/*
 * Lokaler Speicher für Bewertungen und Kommentare (schlechtes Netz beim Seminar).
 *
 * Einträge haben dieselben Namen und Werte wie die bisherigen Cookies:
 *   f<fid>r<einheit>u<user>                       -> JSON {frage_id: antwort}
 *   comment<fid>r<einheit>u<user>[c<kat>]n<0|1>    -> Kommentartext
 *
 * Alles wird sofort in localStorage gespeichert und erst beim Abschicken oder Refresh
 * an /seminar/sync/ geschickt. Ein Eintrag wird erst entfernt, wenn der Server ihn
 * bestätigt hat und er sich seitdem nicht geändert hat – bei Verbindungsabbruch geht
 * also nichts verloren.
 * Ohne localStorage (z.B. gesperrt) werden wie bisher Cookies verwendet.
 *
 * Benötigt die globalen Variablen seminar_sync_url und seminar_user_id.
 */
const SeminarStore = (function () {
    const PREFIX = 'seminar:';
    const KEY_RE = /^(f\d+r\d+u\d+|comment\d+r\d+u\d+(c\d+)?n\d)$/;
    const COOKIE_DAYS = 3;

    let syncing = null;
    const listeners = [];

    const storage = (function () {
        try {
            const test = PREFIX + 'test';
            window.localStorage.setItem(test, '1');
            window.localStorage.removeItem(test);
            return window.localStorage;
        } catch (e) {
            return null;
        }
    })();

    // --- Cookies (Altbestand / Fallback) ---------------------------------------
    function readCookies() {
        const result = {};
        document.cookie.split(';').forEach(function (part) {
            const index = part.indexOf('=');
            if (index < 0) return;
            const name = part.slice(0, index).trim();
            if (KEY_RE.test(name)) {
                result[name] = part.slice(index + 1);
            }
        });
        return result;
    }

    function deleteCookie(name) {
        document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/';
    }

    function migrateCookies() {
        if (!storage) return;
        const cookies = readCookies();
        Object.keys(cookies).forEach(function (name) {
            if (storage.getItem(PREFIX + name) === null) {
                storage.setItem(PREFIX + name, cookies[name]);
            }
            deleteCookie(name);
        });
    }

    // --- Lesen / Schreiben -----------------------------------------------------
    function get(name) {
        if (storage) {
            return storage.getItem(PREFIX + name);
        }
        const value = readCookies()[name];
        return value === undefined ? null : value;
    }

    function set(name, value) {
        if (storage) {
            storage.setItem(PREFIX + name, value);
        } else {
            save_cookies(name, value, COOKIE_DAYS);
        }
        changed();
    }

    function remove(name) {
        if (storage) {
            storage.removeItem(PREFIX + name);
        } else {
            deleteCookie(name);
        }
        changed();
    }

    /* Alle noch nicht gesendeten Einträge der angemeldeten Person */
    function pending() {
        const result = {};
        const userSuffix = new RegExp('u' + seminar_user_id + '(c\\d+)?(n\\d)?$');
        if (storage) {
            for (let i = 0; i < storage.length; i++) {
                const key = storage.key(i);
                if (key && key.startsWith(PREFIX)) {
                    const name = key.slice(PREFIX.length);
                    if (KEY_RE.test(name) && userSuffix.test(name)) {
                        result[name] = storage.getItem(key);
                    }
                }
            }
        } else {
            const cookies = readCookies();
            Object.keys(cookies).forEach(function (name) {
                if (userSuffix.test(name)) result[name] = cookies[name];
            });
        }
        return result;
    }

    /* Anzahl ungesendeter Bewertungen (je Frage) und Kommentare */
    function pendingCount() {
        const entries = pending();
        let count = 0;
        Object.keys(entries).forEach(function (name) {
            if (name.startsWith('comment')) {
                count += 1;
            } else {
                try {
                    count += Object.keys(JSON.parse(entries[name]) || {}).length;
                } catch (e) {
                    count += 1;
                }
            }
        });
        return count;
    }

    function onChange(listener) {
        listeners.push(listener);
        listener(pendingCount());
    }

    function changed() {
        const count = pendingCount();
        listeners.forEach(function (listener) { listener(count); });
    }

    // --- Senden ----------------------------------------------------------------
    function csrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    /*
     * Schickt alle ungesendeten Einträge. Resolved mit der Server-Antwort
     * ({saved, inserted, edited}) oder rejected bei Verbindungs-/Serverfehler.
     */
    function sync(options) {
        options = options || {};
        if (syncing) {
            // Laufende Übertragung abwarten, danach mit dem aktuellen Stand erneut senden
            return syncing.catch(function () {}).then(function () { return sync(options); });
        }
        const entries = pending();
        if (!Object.keys(entries).length && !options.manual) {
            return Promise.resolve({saved: {}, inserted: 0, edited: 0});
        }

        syncing = fetch(seminar_sync_url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
            body: JSON.stringify({entries: entries, manual: !!options.manual}),
        })
            .then(function (response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function (result) {
                Object.keys(result.saved || {}).forEach(function (name) {
                    // Nur entfernen, wenn sich der Eintrag während des Sendens nicht geändert hat
                    if (get(name) === result.saved[name]) {
                        if (storage) storage.removeItem(PREFIX + name); else deleteCookie(name);
                    }
                });
                changed();
                return result;
            })
            .finally(function () {
                syncing = null;
            });
        return syncing;
    }

    /* Bestehende Cookies übernehmen; gesendet wird nur über sync() (Abschicken/Refresh) */
    function start() {
        migrateCookies();
        changed();
    }

    return {
        get: get,
        set: set,
        remove: remove,
        pending: pending,
        pendingCount: pendingCount,
        onChange: onChange,
        sync: sync,
        start: start,
        usesLocalStorage: !!storage,
    };
})();
