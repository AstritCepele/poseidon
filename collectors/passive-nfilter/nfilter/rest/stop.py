import web


class StopR:
    """
    This endpoint is for stopping a filter
    """

    @staticmethod
    def GET(self, filter_id):
        web.header('Content-Type', 'text/html')
        return filter_id
