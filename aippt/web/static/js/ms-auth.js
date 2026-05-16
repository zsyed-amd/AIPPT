/**
 * Microsoft device-code sign-in helper (PRD A).
 *
 * Exposes a single global: `window.msAuth`.
 *
 * Tokens live ONLY in browser localStorage — the server is stateless and never
 * persists Microsoft credentials. The browser is responsible for refreshing
 * before expiry, and `fetchWithAuth()` will attempt a one-shot refresh on 401
 * before giving up.
 */
(function () {
    'use strict';

    var STORAGE_KEYS = {
        accessToken:  'aippt_ms_access_token',
        refreshToken: 'aippt_ms_refresh_token',
        expiresAt:    'aippt_ms_expires_at',   // epoch seconds
        userName:     'aippt_ms_user_name',    // optional cosmetic display
    };

    // Listeners notified whenever the signed-in state changes (sign in / out / refresh failure).
    var stateListeners = [];

    function notifyStateChange() {
        var token = getToken();
        for (var i = 0; i < stateListeners.length; i++) {
            try { stateListeners[i](!!token); } catch (e) { /* swallow */ }
        }
    }

    function onStateChange(fn) {
        if (typeof fn === 'function') {
            stateListeners.push(fn);
            // Fire immediately so callers can sync their UI on registration.
            try { fn(!!getToken()); } catch (e) { /* swallow */ }
        }
    }

    function getToken() {
        return localStorage.getItem(STORAGE_KEYS.accessToken);
    }

    function getUserName() {
        return localStorage.getItem(STORAGE_KEYS.userName);
    }

    function _storeTokens(payload) {
        if (!payload || !payload.access_token) return;
        localStorage.setItem(STORAGE_KEYS.accessToken, payload.access_token);
        if (payload.refresh_token) {
            localStorage.setItem(STORAGE_KEYS.refreshToken, payload.refresh_token);
        }
        if (payload.expires_in) {
            var expiresAt = Math.floor(Date.now() / 1000) + Number(payload.expires_in);
            localStorage.setItem(STORAGE_KEYS.expiresAt, String(expiresAt));
        }
    }

    function signOut() {
        for (var key in STORAGE_KEYS) {
            if (Object.prototype.hasOwnProperty.call(STORAGE_KEYS, key)) {
                localStorage.removeItem(STORAGE_KEYS[key]);
            }
        }
        notifyStateChange();
    }

    /**
     * Try to refresh the access token using the stored refresh token.
     * On success, updates localStorage and returns the new access token.
     * On failure, clears all tokens and returns null.
     */
    function _refresh() {
        var refresh = localStorage.getItem(STORAGE_KEYS.refreshToken);
        if (!refresh) return Promise.resolve(null);
        return fetch('/api/auth/microsoft/refresh', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({refresh_token: refresh}),
        }).then(function (resp) {
            if (!resp.ok) {
                signOut();
                return null;
            }
            return resp.json().then(function (data) {
                _storeTokens(data);
                notifyStateChange();
                return data.access_token || null;
            });
        }).catch(function () {
            signOut();
            return null;
        });
    }

    /**
     * fetch() wrapper that attaches the current Bearer token (if any) and
     * tries a one-shot refresh on 401 before re-raising the failure.
     */
    function fetchWithAuth(url, opts) {
        opts = opts || {};
        var headers = new Headers(opts.headers || {});
        var token = getToken();
        if (token) headers.set('Authorization', 'Bearer ' + token);
        var first = fetch(url, Object.assign({}, opts, {headers: headers}));
        return first.then(function (resp) {
            if (resp.status !== 401) return resp;
            // One-shot refresh + retry.
            return _refresh().then(function (newToken) {
                if (!newToken) return resp;
                var retryHeaders = new Headers(opts.headers || {});
                retryHeaders.set('Authorization', 'Bearer ' + newToken);
                return fetch(url, Object.assign({}, opts, {headers: retryHeaders}));
            });
        });
    }

    // --- Device-code sign-in UI -------------------------------------------------

    function _el(tag, attrs, text) {
        var node = document.createElement(tag);
        if (attrs) {
            for (var k in attrs) {
                if (Object.prototype.hasOwnProperty.call(attrs, k)) {
                    node.setAttribute(k, attrs[k]);
                }
            }
        }
        if (text != null) node.textContent = String(text);
        return node;
    }

    function _ensureModal() {
        var modal = document.getElementById('ms-auth-modal');
        if (modal) return modal;
        modal = document.createElement('dialog');
        modal.id = 'ms-auth-modal';

        var article = _el('article', {style: 'max-width: 28rem;'});

        var header = document.createElement('header');
        header.appendChild(_el('strong', null, 'Sign in to Microsoft'));
        article.appendChild(header);

        var bodyDiv = _el('div', {id: 'ms-auth-body'});
        bodyDiv.appendChild(_el('p', {style: 'margin:0 0 0.5rem 0;'}, 'Starting sign-in…'));
        article.appendChild(bodyDiv);

        var footer = _el('footer', {style: 'display:flex; justify-content:flex-end; gap:0.5rem;'});
        var cancelBtn = _el('button', {class: 'secondary outline', id: 'ms-auth-cancel'}, 'Cancel');
        footer.appendChild(cancelBtn);
        article.appendChild(footer);

        modal.appendChild(article);
        document.body.appendChild(modal);
        cancelBtn.addEventListener('click', function () { modal.close(); });
        return modal;
    }

    function _renderDeviceCode(modal, info) {
        var body = modal.querySelector('#ms-auth-body');
        var safeCode = String(info.user_code || '');
        // Only allow https:// URIs. A javascript: URL in verification_uri would
        // execute on click and could exfiltrate tokens from localStorage.
        // (`_el` and direct document.createElement calls below render everything
        // as text — never as HTML — so user_code/verification_uri can't be parsed.)
        var rawUri = String(info.verification_uri || '');
        var safeUri = rawUri.indexOf('https://') === 0 ? rawUri : '';

        // Clear prior contents (replacing the "Starting sign-in..." placeholder).
        while (body.firstChild) body.removeChild(body.firstChild);

        body.appendChild(_el('p',
            {style: 'margin:0 0 0.75rem 0;'},
            'Open this URL in a browser and enter the code:'));

        var uriP = document.createElement('p');
        uriP.setAttribute('style', 'margin:0 0 0.25rem 0;');
        if (safeUri) {
            var a = document.createElement('a');
            a.id = 'ms-auth-uri';
            a.target = '_blank';
            a.rel = 'noopener';
            a.href = safeUri;
            a.textContent = safeUri;
            uriP.appendChild(a);
        } else {
            uriP.appendChild(_el('span', {id: 'ms-auth-uri'},
                'Invalid verification URL — please try signing in again.'));
        }
        body.appendChild(uriP);

        var row = _el('div', {style: 'display:flex; align-items:center; gap:0.5rem; margin:0.75rem 0;'});
        row.appendChild(_el('code',
            {id: 'ms-auth-code', style: 'font-size:1.4rem; padding:0.35rem 0.6rem;'},
            safeCode));
        var copyBtn = _el('button',
            {class: 'outline', id: 'ms-auth-copy',
             style: 'width:auto; padding:0.25rem 0.6rem; margin:0;'},
            'Copy code');
        row.appendChild(copyBtn);
        body.appendChild(row);

        body.appendChild(_el('p',
            {id: 'ms-auth-status',
             style: 'margin:0; color:var(--pico-muted-color); font-size:0.85rem;'},
            'Waiting for sign-in…'));

        copyBtn.addEventListener('click', function () {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(safeCode).then(function () {
                    copyBtn.textContent = 'Copied!';
                    setTimeout(function () { copyBtn.textContent = 'Copy code'; }, 1500);
                });
            }
        });
    }

    function _setStatus(modal, text) {
        var el = modal.querySelector('#ms-auth-status');
        if (el) el.textContent = text;
    }

    /**
     * Run the full device-code dance: start → render code → poll → store tokens.
     * Returns a promise resolving to the access token (string) on success or
     * null if the user cancels or auth fails.
     */
    function signIn() {
        var modal = _ensureModal();
        modal.showModal();
        var cancelled = false;
        modal.addEventListener('close', function onClose() {
            cancelled = true;
            modal.removeEventListener('close', onClose);
        });

        return fetch('/api/auth/microsoft/start', {method: 'POST'})
            .then(function (resp) {
                if (!resp.ok) {
                    return resp.json().catch(function () { return {}; }).then(function (data) {
                        throw new Error(data.error || 'Failed to start sign-in');
                    });
                }
                return resp.json();
            })
            .then(function (info) {
                _renderDeviceCode(modal, info);
                var intervalSec = Math.max(1, Number(info.interval) || 5);
                var expiresInMs = (Number(info.expires_in) || 900) * 1000;
                var deadline = Date.now() + expiresInMs;
                return _pollLoop(modal, info.device_code, intervalSec, deadline, function () { return cancelled; });
            })
            .then(function (token) {
                if (token) {
                    _setStatus(modal, 'Signed in.');
                    setTimeout(function () { try { modal.close(); } catch (e) { /* ignore */ } }, 600);
                }
                return token;
            })
            .catch(function (err) {
                _setStatus(modal, 'Sign-in failed: ' + (err && err.message ? err.message : err));
                return null;
            });
    }

    function _pollLoop(modal, deviceCode, intervalSec, deadline, isCancelled) {
        return new Promise(function (resolve) {
            function step() {
                if (isCancelled()) return resolve(null);
                if (Date.now() > deadline) {
                    _setStatus(modal, 'Sign-in code expired. Please try again.');
                    return resolve(null);
                }
                fetch('/api/auth/microsoft/poll', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({device_code: deviceCode}),
                }).then(function (resp) {
                    if (resp.status === 401) {
                        // expired_token or declined
                        return resp.json().catch(function () { return {}; }).then(function (data) {
                            _setStatus(modal, data.error || 'Sign-in was rejected or expired.');
                            resolve(null);
                        });
                    }
                    return resp.json().then(function (data) {
                        if (data.status === 'pending') {
                            setTimeout(step, intervalSec * 1000);
                            return;
                        }
                        if (data.status === 'slow_down') {
                            intervalSec = intervalSec + 5;
                            setTimeout(step, intervalSec * 1000);
                            return;
                        }
                        if (data.status === 'ok' && data.access_token) {
                            _storeTokens(data);
                            notifyStateChange();
                            resolve(data.access_token);
                            return;
                        }
                        // Unknown shape — bail.
                        _setStatus(modal, 'Unexpected response from sign-in.');
                        resolve(null);
                    });
                }).catch(function () {
                    _setStatus(modal, 'Network error while polling.');
                    resolve(null);
                });
            }
            step();
        });
    }

    window.msAuth = {
        signIn:         signIn,
        signOut:        signOut,
        getToken:       getToken,
        getUserName:    getUserName,
        fetchWithAuth:  fetchWithAuth,
        onStateChange:  onStateChange,
    };
})();
