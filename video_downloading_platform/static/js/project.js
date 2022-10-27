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
    const notification = jQuery(`#notif-${id}`);
    notification.hide();
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

function show_modal_form(url) {
    jQuery.get(url, function (data) {
        const container = jQuery('#container');
        container.append(data);
        const modal = jQuery('#formModal');
        modal.modal('show');
        modal.on('hidden.bs.modal', event => {
            modal.remove();
        })
    })
}

class FileUpload {
    constructor(input_elt, success_callback, progress_callback, error_callback) {
        this.input = input_elt;
        this.success_callback = success_callback;
        this.progress_callback = progress_callback;
        this.error_callback = error_callback;
        this.max_length = 10000000; //2 * 1024 * 1024;
        this.next_addr = 0;
        this.slices = {};
    }

    create_progress_bar() {
        var progress = `<div class="file-details">
                            <div class="progress" style="margin-top: 5px;">
                                <div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" style="width: 0%">
                                </div>
                            </div>
                            <span id="upload_status" class="text-muted"></span>
                        </div>`
        document.getElementById('uploaded_files').innerHTML = progress
    }

    upload() {
        this.create_progress_bar();
        this.init_file_upload();
    }

    handle_upload_initialization(self, data) {
        self.next_addr = data['next_addr'];
        self.upload_file();
    }

    async init_file_upload() {
        const self = this;
        self.file = self.input.files[0];
        await self.init_file_slices()
        $.ajaxSetup({
            async: true,
            headers: {
                "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
            }
        });
        const payload = {
            'file_name': self.file_name,
            'file_size': self.file_size,
            'chunks': self.slices,
        }
        await $.ajax({
            url: '/upload',
            method: 'POST',
            data: JSON.stringify(payload),
            contentType:'application/json; charset=utf-8',
            dataType: 'json',
            success: function (data) {
                self.upload_request = data;
                self.next_addr = data['next_addr'];
                self.upload_file(self);
            }
        })
    }

    async init_file_slices () {
        const me = this;
        this.file_size = this.file.size;
        this.file_name = this.file.name;
        let addr = 0;
        $('#upload_status').text('Hashing')
        while(addr < this.file_size) {
            let next_chunk = addr + this.max_length + 1 ;
            const chunk = this.file.slice(addr, next_chunk);
            const buf = await chunk.arrayBuffer()
            const bin_hash = await crypto.subtle.digest('SHA-256', buf)
            const hash_array = Array.from(new Uint8Array(bin_hash))
            const hash = hash_array.map(b => b.toString(16).padStart(2, '0')).join('');
            me.slices[addr]=hash;
            addr = next_chunk;
        }
    }

    upload_file(self) {
        $('#upload_status').text('Uploading')
        var end;
        var start_addr = self.next_addr;
        const formData = new FormData();
        var nextChunk = start_addr + self.max_length + 1;
        var currentChunk = self.file.slice(start_addr, nextChunk);
        var uploadedChunk = start_addr + currentChunk.size
        if (uploadedChunk >= self.file.size) {
            end = 1;
        } else {
            end = 0;
        }
        formData.append('file', currentChunk)
        formData.append('addr', start_addr)
        formData.append('eof', end)
        let percent = 0
        if (self.file.size < self.max_length) {
            percent = Math.round((uploadedChunk / self.file.size) * 100);
        } else {
            percent = Math.round((uploadedChunk / self.file.size) * 100);
        }
        $('.progress-bar').css('width', percent + '%')
        $('.progress-bar').text(percent + '%')
        $.ajaxSetup({
            async: true,
            headers: {
                "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
            }
        });
        $.ajax({
            url: `/upload/${self.upload_request.id}`,
            type: 'POST',
            dataType: 'json',
            cache: false,
            processData: false,
            contentType: false,
            data: formData,
            error: function (xhr) {
                self.error_callback(xhr)
            },
            success: function (res) {
                self.upload_request = res
                self.next_addr = res['next_addr']
                if (self.next_addr > 0) {
                    self.progress_callback(self.upload_request, uploadedChunk, self.file.size);
                    // upload file in chunks
                    self.upload_file(self);
                } else {
                    // upload complete
                    $('#upload_status').text('Success!')
                    self.success_callback(self.upload_request);
                }
            }
        });
    };
}
