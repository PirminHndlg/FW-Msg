function get_cookies(name = undefined) {
    let cookies = document.cookie.split(';')
    let cookie_dict = {}
    for (const cookie of cookies) {
        let [key, value] = cookie.split('=')
        if (name !== undefined) {
            // console.log(key, value, name)
            if (key.replace(/\s/g, "") === name) {
                if (value === "") {
                    return false
                }
                return value
            } else {
                continue
            }
        }
        cookie_dict[key] = value
    }

    if (name !== undefined) {
        return false
    }

    if (cookie_dict !== {}) {
        return cookie_dict
    }
    return false
}

function remove_cookies(name) {
    console.log("remove cookie" + name)
    document.cookie = name + '=""; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/';
}

function save_cookies(name, value, days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
}


function postForm(path, params) {
    let form = document.createElement('form');
    form.setAttribute('method', 'post');
    form.setAttribute('action', path);

    for (var key in params) {
        if (params.hasOwnProperty(key)) {
            var hiddenField = document.createElement('input');
            hiddenField.setAttribute('type', 'hidden');
            hiddenField.setAttribute('name', key);
            hiddenField.setAttribute('value', params[key]);

            form.appendChild(hiddenField);
        }
    }

    document.body.appendChild(form);
    form.submit();
}

function checkStringFormat(str) {
    // Regular expression to match the pattern
    return true

    const pattern = /^[a-zA-Z]\d[a-zA-Z]\d[a-zA-Z][a-zA-Z]\d[a-zA-Z]\d\d$/;
    return pattern.test(str);
}

function refresh(only = undefined) {
    let cookies = document.cookie.split(';')

    let data = {}

    for (const cookie of cookies) {
        let [key, value] = cookie.split('=')
        if (checkStringFormat(key)) {
            if (only !== undefined) {
                if (key.includes(`f${only}q`)) {
                    data[key] = value
                }
            } else {
                data[key] = value
            }
        }
    }

    console.log(data)
    data['refresh'] = true

    postForm(refresh_url, data)
}

function http(url) {
    try {
        let request = new XMLHttpRequest();
        request.open("GET", url, false);
        request.send(null);

        if (request.status === 404) {
            return
        }
        console.log(request.responseText)
        return request.responseText;
    } catch (e) {
        console.log(e)
    }
}