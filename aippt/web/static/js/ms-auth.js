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

    var NTID_KEY = 'aippt_ntid';

    // Regex that the server's _ntid_or_400 uses (allowlist guard).
    var NTID_RE = /^[A-Za-z0-9._-]+$/;

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
        localStorage.removeItem(NTID_KEY);
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
        return fetch('api/auth/microsoft/refresh', {
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
        // Per-user SharePoint render-staging folders are keyed by NTID.
        // The 'aippt_ntid' key is populated at sign-in (NTID step of the modal);
        // we forward it so the Linux Graph render path can write to the user's
        // subfolder instead of a shared 'anonymous' one.
        var ntid = (localStorage.getItem(NTID_KEY) || '').trim();
        if (ntid) headers.set('X-AIPPT-NTID', ntid);
        var first = fetch(url, Object.assign({}, opts, {headers: headers}));
        return first.then(function (resp) {
            if (resp.status !== 401) return resp;
            // One-shot refresh + retry.
            return _refresh().then(function (newToken) {
                if (!newToken) return resp;
                var retryHeaders = new Headers(opts.headers || {});
                retryHeaders.set('Authorization', 'Bearer ' + newToken);
                if (ntid) retryHeaders.set('X-AIPPT-NTID', ntid);
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

        // NTID step
        var ntidStep = _el('div', {id: 'ms-auth-ntid-step'});
        ntidStep.appendChild(_el('p',
            {style: 'margin:0 0 0.75rem 0; font-weight:600;'},
            'Enter your NTID to sign in'));

        var label = document.createElement('label');
        label.htmlFor = 'ms-auth-ntid-field';
        label.textContent = 'NTID';
        label.style.cssText = 'display:block; margin-bottom:0.25rem; font-size:0.9rem;';
        ntidStep.appendChild(label);

        var ntidInput = _el('input', {
            type: 'text',
            id: 'ms-auth-ntid-field',
            placeholder: 'e.g. melliott',
            autocomplete: 'username',
            style: 'margin-bottom:0.25rem;',
        });
        ntidStep.appendChild(ntidInput);

        var ntidError = _el('p', {
            id: 'ms-auth-ntid-error',
            style: 'margin:0 0 0.5rem 0; color:var(--pico-del-color, #c0392b); font-size:0.8rem; min-height:1.1rem;',
        }, '');
        ntidStep.appendChild(ntidError);

        article.appendChild(ntidStep);

        // Device-code step (hidden initially)
        var codeStep = _el('div', {
            id: 'ms-auth-code-step',
            style: 'display:none;',
        });
        codeStep.appendChild(_el('p',
            {style: 'margin:0 0 0.5rem 0; color:var(--pico-muted-color); font-size:0.85rem;'},
            'Starting sign-in…'));
        article.appendChild(codeStep);

        var footer = _el('footer', {style: 'display:flex; justify-content:flex-end; gap:0.5rem;'});
        var cancelBtn = _el('button', {class: 'secondary outline', id: 'ms-auth-cancel'}, 'Cancel');
        var continueBtn = _el('button', {
            id: 'ms-auth-continue',
            disabled: 'disabled',
        }, 'Continue');
        footer.appendChild(cancelBtn);
        footer.appendChild(continueBtn);
        article.appendChild(footer);

        modal.appendChild(article);
        document.body.appendChild(modal);
        cancelBtn.addEventListener('click', function () { modal.close(); });

        // Validate NTID on every keystroke
        ntidInput.addEventListener('input', function () {
            var val = ntidInput.value.trim();
            var valid = val.length > 0 && NTID_RE.test(val);
            continueBtn.disabled = !valid;
            if (val.length > 0 && !NTID_RE.test(val)) {
                ntidError.textContent =
                    'Use letters, numbers, dot, underscore, or hyphen only';
            } else {
                ntidError.textContent = '';
            }
        });

        return modal;
    }

    /**
     * Render the NTID entry step. Pre-fills from localStorage if available.
     * Returns a Promise that resolves to the validated NTID string when the
     * user clicks Continue, or null if they click Cancel / close the modal.
     */
    function _renderNtidStep(modal) {
        var ntidStep = modal.querySelector('#ms-auth-ntid-step');
        var codeStep = modal.querySelector('#ms-auth-code-step');
        var continueBtn = modal.querySelector('#ms-auth-continue');
        var cancelBtn = modal.querySelector('#ms-auth-cancel');
        var ntidInput = modal.querySelector('#ms-auth-ntid-field');
        var ntidError = modal.querySelector('#ms-auth-ntid-error');

        // Show NTID step, hide code step
        ntidStep.style.display = '';
        codeStep.style.display = 'none';
        continueBtn.style.display = '';
        cancelBtn.style.display = '';

        // Pre-fill from localStorage
        var saved = (localStorage.getItem(NTID_KEY) || '').trim();
        ntidInput.value = saved;
        ntidError.textContent = '';
        var preValid = saved.length > 0 && NTID_RE.test(saved);
        continueBtn.disabled = !preValid;

        // If nothing is saved yet but the user already has a token (e.g. the
        // "edit" path or a returning session), seed the field from the
        // signed-in identity so the common case is typo-proof. Best-effort and
        // non-blocking: if the user focuses/types first we leave their input
        // alone. The server still gates on the explicit header — this only
        // changes the default value.
        if (!saved && getToken()) {
            fetch('api/auth/whoami', {
                headers: {'Authorization': 'Bearer ' + getToken()},
            }).then(function (resp) {
                return resp.ok ? resp.json() : null;
            }).then(function (data) {
                var hint = data && data.suggested_ntid;
                if (hint && !ntidInput.value.trim()) {
                    ntidInput.value = hint;
                    continueBtn.disabled = !NTID_RE.test(hint);
                    ntidError.textContent = '';
                }
            }).catch(function () { /* swallow — seeding is optional */ });
        }

        return new Promise(function (resolve) {
            var resolved = false;

            function onContinue() {
                if (resolved) return;
                var val = ntidInput.value.trim();
                if (!val || !NTID_RE.test(val)) return;
                resolved = true;
                cleanup();
                resolve(val);
            }

            function onCancel() {
                if (resolved) return;
                resolved = true;
                cleanup();
                resolve(null);
            }

            function onClose() {
                if (resolved) return;
                resolved = true;
                cleanup();
                resolve(null);
            }

            function onKeydown(e) {
                if (e.key === 'Enter') onContinue();
            }

            function cleanup() {
                continueBtn.removeEventListener('click', onContinue);
                cancelBtn.removeEventListener('click', onCancel);
                modal.removeEventListener('close', onClose);
                ntidInput.removeEventListener('keydown', onKeydown);
            }

            continueBtn.addEventListener('click', onContinue);
            cancelBtn.addEventListener('click', onCancel);
            modal.addEventListener('close', onClose);
            ntidInput.addEventListener('keydown', onKeydown);

            // Focus the input
            setTimeout(function () { ntidInput.focus(); }, 50);
        });
    }

    function _renderDeviceCode(modal, info, ntid) {
        var ntidStep = modal.querySelector('#ms-auth-ntid-step');
        var codeStep = modal.querySelector('#ms-auth-code-step');
        var continueBtn = modal.querySelector('#ms-auth-continue');

        // Switch to code step
        ntidStep.style.display = 'none';
        codeStep.style.display = '';
        continueBtn.style.display = 'none';

        var safeCode = String(info.user_code || '');
        // Only allow https:// URIs. A javascript: URL in verification_uri would
        // execute on click and could exfiltrate tokens from localStorage.
        // (`_el` and direct document.createElement calls below render everything
        // as text — never as HTML — so user_code/verification_uri can't be parsed.)
        var rawUri = String(info.verification_uri || '');
        var safeUri = rawUri.indexOf('https://') === 0 ? rawUri : '';

        // Clear prior contents.
        while (codeStep.firstChild) codeStep.removeChild(codeStep.firstChild);

        // NTID line with "edit" link
        var ntidLine = document.createElement('p');
        ntidLine.style.cssText =
            'margin:0 0 0.75rem 0; font-size:0.85rem; color:var(--pico-muted-color);';
        var ntidLabel = document.createTextNode('NTID: ' + String(ntid) + ' ');
        ntidLine.appendChild(ntidLabel);
        var editLink = document.createElement('a');
        editLink.href = '#';
        editLink.textContent = '(edit)';
        editLink.style.cssText = 'font-size:0.8rem;';
        ntidLine.appendChild(editLink);
        codeStep.appendChild(ntidLine);

        codeStep.appendChild(_el('p',
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
        codeStep.appendChild(uriP);

        var row = _el('div', {style: 'display:flex; align-items:center; gap:0.5rem; margin:0.75rem 0;'});
        row.appendChild(_el('code',
            {id: 'ms-auth-code', style: 'font-size:1.4rem; padding:0.35rem 0.6rem;'},
            safeCode));
        var copyBtn = _el('button',
            {class: 'outline', id: 'ms-auth-copy',
             style: 'width:auto; padding:0.25rem 0.6rem; margin:0;'},
            'Copy code');
        row.appendChild(copyBtn);
        codeStep.appendChild(row);

        codeStep.appendChild(_el('p',
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

        // "edit" goes back to NTID step — caller must handle; we signal via a
        // rejected promise so the outer signIn() can restart.
        return new Promise(function (resolve) {
            editLink.addEventListener('click', function (e) {
                e.preventDefault();
                resolve('edit');
            });
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

        return _doSignIn(modal);
    }

    function _doSignIn(modal) {
        var cancelled = false;

        function onModalClose() {
            cancelled = true;
        }
        modal.addEventListener('close', onModalClose);

        // Step 1: NTID entry
        return _renderNtidStep(modal).then(function (ntid) {
            modal.removeEventListener('close', onModalClose);

            if (!ntid) {
                // User cancelled at NTID step
                if (!modal.open) {
                    // Modal already closed by Cancel
                } else {
                    modal.close();
                }
                return null;
            }

            // Save NTID now so fetchWithAuth picks it up immediately
            localStorage.setItem(NTID_KEY, ntid);

            // Re-register close listener for the code step
            cancelled = false;
            modal.addEventListener('close', onModalClose);

            // Step 2: device-code flow
            return fetch('api/auth/microsoft/start', {method: 'POST'})
                .then(function (resp) {
                    if (!resp.ok) {
                        return resp.json().catch(function () { return {}; }).then(function (data) {
                            throw new Error(data.error || 'Failed to start sign-in');
                        });
                    }
                    return resp.json();
                })
                .then(function (info) {
                    var editPromise = _renderDeviceCode(modal, info, ntid);
                    var intervalSec = Math.max(1, Number(info.interval) || 5);
                    var expiresInMs = (Number(info.expires_in) || 900) * 1000;
                    var deadline = Date.now() + expiresInMs;

                    var pollPromise = _pollLoop(modal, info.device_code, intervalSec, deadline,
                        function () { return cancelled; });

                    // Race: poll completes OR user clicks "edit"
                    return Promise.race([
                        pollPromise.then(function (token) { return {type: 'poll', token: token}; }),
                        editPromise.then(function (sig) { return {type: sig}; }),
                    ]);
                })
                .then(function (result) {
                    modal.removeEventListener('close', onModalClose);

                    if (result.type === 'edit') {
                        // User wants to correct their NTID — restart from NTID step.
                        // The device code is abandoned (they'll get a new one on Continue).
                        if (modal.open) {
                            return _doSignIn(modal);
                        }
                        return null;
                    }

                    var token = result.token;
                    if (token) {
                        _setStatus(modal, 'Signed in.');
                        setTimeout(function () {
                            try { modal.close(); } catch (e) { /* ignore */ }
                        }, 600);
                    }
                    return token || null;
                })
                .catch(function (err) {
                    modal.removeEventListener('close', onModalClose);
                    _setStatus(modal, 'Sign-in failed: ' + (err && err.message ? err.message : err));
                    return null;
                });
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
                fetch('api/auth/microsoft/poll', {
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
