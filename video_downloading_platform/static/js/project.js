var toaster_shown = false;

function toggle_toaster() {
    const toastLive = jQuery('#notification_toaster');
    toastLive.children().each(function (idx, val) {
        const toast = new bootstrap.Toast(jQuery(this));
        if (jQuery(this).hasClass('show')) {
            toast.hide();
            toaster_shown = false;
        } else {
            toast.show();
            toaster_shown = true;
        }
    })
}

function reapply_toaster_visibility() {
    const toastLive = jQuery('#notification_toaster');
    toastLive.children().each(function (idx, val) {
        const toast = new bootstrap.Toast(jQuery(this));
        if (toaster_shown) {
            toast.show();
        } else {
            toast.hide();
        }
    })
}

function mark_notif_as_read(id) {
    jQuery.get(`/inbox/notifications/delete/${id}`);
    fetch_api_data();
}

function notification_toaster_callback(data) {
    const toaster = jQuery('#notification_toaster');
    jQuery.get('/notifications', function (msg) {
        toaster.html(msg);
        reapply_toaster_visibility();
    })
}

function update_batch_statuses() {
    jQuery.get('/batch/statuses', function (data) {
        data.forEach(function (elt) {
            const submitted_counter = jQuery(`#${elt.id}_submitted`);
            const succeeded_counter = jQuery(`#${elt.id}_succeeded`);
            const failed_counter = jQuery(`#${elt.id}_failed`);
            submitted_counter.text(elt.submitted);
            succeeded_counter.text(elt.succeeded);
            failed_counter.text(elt.failed);
        })
    })

    setTimeout(update_batch_statuses, 10000);
}
