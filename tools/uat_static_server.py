from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
    host, port = '127.0.0.1', 8000
    print(f'[KU Open DA UAT] No-cache frontend server: http://{host}:{port}/')
    ThreadingHTTPServer((host, port), NoCacheHandler).serve_forever()
