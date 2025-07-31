
function delete_all_cookies() {
    let cookies = document.cookie.split(';')

    for (const cookie of cookies) {
        let [key, value] = cookie.split('=')
        if (key !== 'session') {
            document.cookie = key + '=; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
        }
    }
}