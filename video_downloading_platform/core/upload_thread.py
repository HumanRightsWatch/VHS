from threading import Thread

class UploadCompletionThread(Thread):
    def __init__(self, upload_request_id, download_request_id):
        self.upload_request_id = upload_request_id
        self.download_request_id = download_request_id
        super().__init__()

    def run(self) -> None:
        pass
