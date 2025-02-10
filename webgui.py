import os
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import mimetypes
import json
from transformdata import DataTransformer
from filedialog import get_save_dialog

UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'csv', 'json', 'sqlite', 'xml'}

class MultipartFormParser:
    """Custom parser for multipart/form-data without deprecated cgi module"""
    def __init__(self, environ):
        self.boundary = environ.get('boundary').encode()
        self.content_length = int(environ.get('content-length', 0))
        self.input_stream = environ.get('wsgi.input')
        self._fields = {}
        self._files = {}
        self._parse()

    def _parse(self):
        # read the entire input stream
        data = self.input_stream.read(self.content_length)
        
        # split on boundary and remove first and last parts
        parts = data.split(b'--' + self.boundary)[1:-1]
        
        for part in parts:
            # remove leading and trailing \r\n
            part = part.strip(b'\r\n')
            
            # split headers and content
            try:
                headers_raw, content = part.split(b'\r\n\r\n', 1)
                headers = dict(line.split(': ', 1) for line in 
                             headers_raw.decode().split('\r\n') if ': ' in line)
                
                # parse content disposition
                disp_header = headers.get('Content-Disposition', '')
                disp_params = dict(param.strip().split('=', 1) for param in 
                                 disp_header.split(';')[1:] if '=' in param)
                
                name = disp_params.get('"name"', disp_params.get('name', '')).strip('"')
                
                if 'filename' in disp_params:
                    filename = disp_params['filename'].strip('"')
                    if filename:
                        self._files[name] = {
                            'filename': filename,
                            'content': content,
                            'content-type': headers.get('Content-Type', 
                                          'application/octet-stream')
                        }
                else:
                    self._fields[name] = content.decode().strip()
            except Exception as e:
                print(f"Error parsing part: {e}")

    def getvalue(self, key, default=None):
        """Get a form field value"""
        return self._fields.get(key, default)

    def getfile(self, key):
        """Get a file field"""
        return self._files.get(key)

class DataTransformerHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.transformer = DataTransformer()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        
        try:
            file_path = os.path.join(os.path.dirname(__file__), 'templates', self.path.lstrip('/'))
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(self.path)[0] or 'text/plain')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, 'File not found')

    def do_POST(self):
        if self.path == '/convert':
            self.handle_convert()
        elif self.path == '/generate':
            self.handle_generate()
        else:
            self.send_error(404, 'Not found')

    def handle_convert(self):
        try:
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, 'Expected multipart/form-data')
                return

            boundary = content_type.split('boundary=')[1].strip()
            environ = {
                'boundary': boundary,
                'content-length': self.headers.get('Content-Length', 0),
                'wsgi.input': self.rfile
            }
            
            form = MultipartFormParser(environ)
            file_data = form.getfile('file')
            
            if not file_data:
                self.send_error(400, 'No file provided')
                return

            filename = file_data['filename']
            if not filename:
                self.send_error(400, 'No file selected')
                return

            output_format = form.getvalue('output_format')
            if not output_format:
                self.send_error(400, 'No output format specified')
                return

            # save uploaded file
            input_path = os.path.join(UPLOAD_FOLDER, filename)
            with open(input_path, 'wb') as f:
                f.write(file_data['content'])

            try:
                input_format = filename.rsplit('.', 1)[1].lower()
                flatten = form.getvalue('flatten') == 'true'
                table_name = form.getvalue('table')

                # special handling for SQLite input, to list tables
                if input_format == 'sqlite':
                    # only prompt for tables on first request (without table parameter)
                    if not table_name:
                        tables = self.transformer.list_sqlite_tables(input_path)
                        if not tables:
                            self.send_error(400, "No tables found in SQLite database")
                            os.unlink(input_path)
                            return
                        
                        # send table list to client
                        response_data = {
                            "type": "tables",
                            "tables": tables,
                            "message": "Select a table or choose 'All Tables'"
                        }
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(response_data).encode())
                        return

                # rest of the conversion logic
                # show save dialog first
                base_name = "converted_tables" if table_name == '*' else "converted"
                output_path = get_save_dialog(
                    title="Save Converted File",
                    default_name=f"{base_name}.{output_format}"
                )
                
                if not output_path:  # user cancelled
                    os.unlink(input_path)
                    return

                # convert with table name (None means all tables, note: might better to force choosing, since sqlite might be very large)
                table = None if table_name == '*' else table_name
                self.transformer.convert(input_path, output_path, 
                                      input_format, output_format, 
                                      table=table,
                                      flatten=flatten)
                
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"success")

            finally:
                if os.path.exists(input_path):
                    os.unlink(input_path)

        except Exception as e:
            self.send_error(500, str(e))

    def handle_generate(self):
        try:
            # form data needs to be parsed
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            form_data = parse_qs(post_data)

            # get row count and format
            try:
                rows = int(form_data.get('rows', ['100'])[0])
                if rows < 1:
                    raise ValueError("Row count must be positive")
            except ValueError:
                self.send_error(400, "Invalid row count")
                return

            selected_format = form_data.get('format', ['csv'])[0]
            if selected_format not in ALLOWED_EXTENSIONS:
                self.send_error(400, "Invalid format")
                return

            # ask user for save location using native file dialog of the OS
            default_ext = f'.{selected_format}'
            output_path = get_save_dialog(
                title="Save Generated Data",
                default_name=f"generated.{selected_format}"
            )
            
            if not output_path:  # user cancelled
                self.send_error(400, "Operation cancelled")
                return

            # extract format from actual file path
            output_format = output_path.rsplit('.', 1)[1].lower()
            if output_format not in ALLOWED_EXTENSIONS:
                self.send_error(400, "Invalid output format")
                return

            # generate data
            self.transformer.generate_data(rows, output_path, output_format)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"Generated {rows} rows of data in {output_format} format!".encode())

        except Exception as e:
            self.send_error(500, str(e))

def run(port=8000):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    server = HTTPServer(('localhost', port), DataTransformerHandler)
    print(f'Starting server on http://localhost:{port}') # localhost, note: research if these need to be changed for packaging and distribution
    server.serve_forever()

if __name__ == '__main__':
    run()
