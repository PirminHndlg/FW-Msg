document.addEventListener('DOMContentLoaded', function() {
    return;

    console.log('window.calendarEvents', window.calendarEvents);
    console.log('document.getElementById', document.getElementById('calendar'));

    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;

    // Get configuration from window object
    const config = window.calendarConfig || {};
    const isSmall = config.small || false;
    const showViewToggle = config.showViewToggle || false;
    const dynamicHeight = config.dynamicHeight || false;

    function updateCalendarSize(view) {
        if (!dynamicHeight) return;
        
        if (view === 'dayGridWeek') {
            calendarEl.classList.add('small-view');
            calendarEl.classList.remove('large-view');
        } else {
            calendarEl.classList.add('large-view');
            calendarEl.classList.remove('small-view');
        }
    }

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: config.initialView || 'dayGridMonth',
        locale: 'de',
        headerToolbar: {
            left: isSmall ? '' : 'prev,next',
            center: isSmall ? '' : 'title',
            right: isSmall ? '' : 'today'
        },
        height: isSmall && !dynamicHeight ? 400 : 'auto',
        events: window.calendarEvents || [],
        viewDidMount: function(info) {
            updateCalendarSize(info.view.type);
        },
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

    // Set initial size
    updateCalendarSize(calendar.view.type);

    // Add view toggle functionality if enabled
    if (showViewToggle) {
        document.getElementById('weekViewBtn').addEventListener('click', function() {
            calendar.changeView('dayGridWeek');
            updateCalendarSize('dayGridWeek');
            this.classList.add('active');
            document.getElementById('monthViewBtn').classList.remove('active');
        });

        document.getElementById('monthViewBtn').addEventListener('click', function() {
            calendar.changeView('dayGridMonth');
            updateCalendarSize('dayGridMonth');
            this.classList.add('active');
            document.getElementById('weekViewBtn').classList.remove('active');
        });

        // Set initial active state
        if (config.initialView === 'dayGridWeek') {
            document.getElementById('weekViewBtn').classList.add('active');
        } else {
            document.getElementById('monthViewBtn').classList.add('active');
        }
    }

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