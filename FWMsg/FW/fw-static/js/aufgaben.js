document.addEventListener('DOMContentLoaded', function() {

    console.log('window.calendarEvents', window.calendarEvents);

    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridWeek',
        locale: 'de',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridWeek,dayGridMonth'
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
                new bootstrap.Tooltip(info.el, {
                    title: info.event.title,
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