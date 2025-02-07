document.addEventListener('DOMContentLoaded', function() {

    console.log('window.calendarEvents', window.calendarEvents);
    console.log('document.getElementById', document.getElementById('calendar'));

    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'de',
        headerToolbar: {
            left: 'prev,next',
            center: 'title',
            right: 'today'
        },
        height: 'auto',
        events: window.calendarEvents || [],
        eventClick: function(info) {
            if (info.event.url) {
                window.location.href = info.event.url;
                info.jsEvent.preventDefault();
            }
        },
        eventDidMount: function(info) {
            if (typeof bootstrap !== 'undefined') {
                let datetime_format = {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'}
                // If event has no time component, only show the date
                if (info.event.start && info.event.start.getHours() === 0 && info.event.start.getMinutes() === 0) {
                    datetime_format = {day: '2-digit', month: '2-digit', year: 'numeric'};
                }
                
                new bootstrap.Tooltip(info.el, {
                    title: info.event.title + ' ' + info.event.start.toLocaleString([], datetime_format) + ' ' + (info.event.end ? info.event.end.toLocaleString([], datetime_format) : ''),
                    placement: 'top',
                    trigger: 'hover',
                    container: 'body'
                });
            }
        },
        editable: false,
        selectable: false,
        longPressDelay: 0,
        eventLongPressDelay: 0,
        selectLongPressDelay: 0,
        dragScroll: false,
        handleWindowResize: true,
        navLinks: false
    });
    calendar.render();

    let touchStartX = 0;
    let touchEndX = 0;
    
    calendarEl.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    }, false);
    
    calendarEl.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    }, false);
    
    function handleSwipe() {
        const swipeThreshold = 50;
        const swipeDistance = touchEndX - touchStartX;
        
        if (Math.abs(swipeDistance) > swipeThreshold) {
            if (swipeDistance > 0) {
                calendar.prev();
            } else {
                calendar.next();
            }
        }
    }
}); 