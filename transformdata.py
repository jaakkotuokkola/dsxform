import os
import csv
import json
import time
import ctypes
import sqlite3
import logging
import tempfile
import argparse
import mimetypes
from urllib.parse import parse_qs
import xml.etree.ElementTree as ET
from filedialog import get_save_dialog
from http.server import HTTPServer, BaseHTTPRequestHandler

# This python file is a simple tool for converting data between different formats
# And for generating mock data based on given regular expressions
# Using C compiled to a shared library for tokenizing and parsing regex patterns and generating random data

class ASTNode(ctypes.Structure):
    pass

ASTNode._fields_ = [
    ("type", ctypes.c_int), ("value", ctypes.c_char * 256), ("min", ctypes.c_int),
    ("max", ctypes.c_int), ("is_negated", ctypes.c_bool), ("children", ctypes.POINTER(ASTNode)),
    ("num_children", ctypes.c_int)
]

class Token(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("value", ctypes.c_char * 256), ("min", ctypes.c_int),
        ("max", ctypes.c_int), ("is_negated", ctypes.c_bool)
    ]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class DataTransformer:
    def __init__(self, config_path="genconfig.json"):
        self.supported_formats = ['csv', 'json', 'sqlite', 'xml']
        self.config_path = config_path
        # C funtion definitions
        self.lib = ctypes.CDLL('./librandomvalues.so')
        self.lib.tokenize.argtypes = [
            ctypes.c_char_p,                        # Pattern
            ctypes.POINTER(ctypes.POINTER(Token)),  # Pointer to tokens
            ctypes.POINTER(ctypes.c_int)            # Pointer to num_tokens
        ]
        self.lib.tokenize.restype = ctypes.c_int
        self.lib.parse_tokens.argtypes = [
            ctypes.POINTER(Token),                  # Tokens
            ctypes.c_int,                           # Number of tokens
            ctypes.POINTER(ctypes.POINTER(ASTNode)) # Pointer to AST
        ]
        self.lib.parse_tokens.restype = ctypes.c_int
        self.lib.initialize_random()
        self.lib.free_ast.argtypes = [ctypes.POINTER(ASTNode)]
        self.lib.free_ast.restype = None
        self.lib.free_tokens.argtypes = [ctypes.POINTER(Token)]
        self.lib.free_tokens.restype = None
        self._ensure_temp_folders()

    def _ensure_temp_folders(self):
        """Ensure temporary folders exist for web interface file handling."""
        import tempfile
        self.temp_dir = tempfile.gettempdir()
        os.makedirs(self.temp_dir, exist_ok=True)

    def get_temp_path(self, filename):
        """Get a temporary file path."""
        return os.path.join(self.temp_dir, filename)
        
    def is_nested(self, data):
        """Check if data contains nested dictionaries or lists."""
        for item in data:
            for value in item.values():
                if isinstance(value, (dict, list)):
                    return True
        return False
    
    # Logic for flattening nested data structures
    # Flattens them to 1 level
    # Prefixes child keys with parent key and adds index when needed
    # note: might be better to let the user edit structures manually with an interface 
    #       to avoid forcing a specific structure and making the tool useful in more cases
    def flatten_data(self, data):
        """Flatten nested data into a list of flat dictionaries with ordered keys."""
        # Flatten each item and collect all keys in insertion order
        flattened_items = [self._flatten(item) for item in data]
        all_keys = []
        for item in flattened_items:
            for key in item.keys():
                if key not in all_keys:
                    all_keys.append(key)
        return [
            {key: item.get(key, None) for key in all_keys}
            for item in flattened_items
        ]

    def _flatten(self, item, parent_key=''):
        """Recursively flatten nested structures, preserving hierarchy in keys."""
        flattened = {}
        for key, value in item.items():
            new_key = f"{parent_key}_{key}" if parent_key else key
            self._flatten_value(new_key, value, flattened)
        return flattened

    def _flatten_value(self, key, value, flattened):
        """Standardize flattening for both JSON and XML sources."""
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_value is not None:  # Preserve null values
                    self._flatten_value(f"{key}_{sub_key}", sub_value, flattened)
        elif isinstance(value, list):
            if value:  # Process non-empty lists
                for idx, elem in enumerate(value):
                    if isinstance(elem, (dict, list)):
                        # For nested structures (objects/arrays), use consistent indexing
                        self._flatten_value(f"{key}_{idx}", elem, flattened)
                    else:
                        # For primitive arrays, use simpler indexing
                        flattened[f"{key}_{idx}"] = elem
        else:
            flattened[key] = value

    # Functions for reading and writing data in different formats
    # I will expect usual structured data

    def read_csv(self, csv_path):
        """Read CSV and return its data as a list of dictionaries."""
        try:
            with open(csv_path, 'r') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                return [row for row in csv_reader]
        except FileNotFoundError:
            raise ValueError(f"Input file not found: {csv_path}")
        except csv.Error:
            raise ValueError(f"Invalid CSV format: {csv_path}")

    def write_csv(self, data, csv_path):
        """Write data to CSV."""
        if not data:
            return
        headers = list(data[0].keys())
        try:
            with open(csv_path, 'w', newline='') as csv_file:
                csv_writer = csv.DictWriter(csv_file, fieldnames=headers)
                csv_writer.writeheader()
                csv_writer.writerows(data)
        except IOError:
            raise ValueError(f"Unable to write to file: {csv_path}")

    def read_json(self, json_path):
        try:
            with open(json_path, 'r') as json_file:
                return json.load(json_file)
        except FileNotFoundError:
            raise ValueError(f"Input file not found: {json_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format: {json_path}")

    def write_json(self, data, json_path):
        try:
            with open(json_path, 'w') as json_file:
                json.dump(data, json_file, indent=4)
        except IOError:
            raise ValueError(f"Unable to write to file: {json_path}")

    def list_sqlite_tables(self, db_path):
        """List all tables in a SQLite database."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except sqlite3.Error as e:
            raise ValueError(f"Error accessing SQLite database: {str(e)}")

    def read_sqlite(self, db_path, table=None):
        """Read from SQLite, optionally from a specific table."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if table is None:
                # Read all tables
                tables = self.list_sqlite_tables(db_path)
                all_data = {}
                for t in tables:
                    cursor.execute(f'SELECT * FROM {t}')
                    headers = [desc[0] for desc in cursor.description]
                    all_data[t] = [dict(zip(headers, row)) for row in cursor.fetchall()]
                return all_data
            else:
                # Read specific table
                cursor.execute(f'SELECT * FROM {table}')
                data = cursor.fetchall()
                headers = [desc[0] for desc in cursor.description]
                return [dict(zip(headers, row)) for row in data]
        except sqlite3.Error as e:
            raise ValueError(f"Error reading from SQLite: {str(e)}")
        finally:
            conn.close()

    def write_sqlite(self, data, db_path, table):
        if not data:
            return
        headers = list(data[0].keys())
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        columns = ', '.join([f'"{header}" TEXT' for header in headers])
        cursor.execute(f'CREATE TABLE IF NOT EXISTS {table} ({columns})')

        conn.execute("BEGIN TRANSACTION")
        try:
            rows_to_insert = [tuple(row.get(header, None) for header in headers) for row in data]
            placeholders = ', '.join(['?' for _ in headers])
            cursor.executemany(f'INSERT INTO {table} VALUES ({placeholders})', rows_to_insert)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def read_xml(self, xml_path):
        """Read XML preserving nested structures consistently with JSON."""
        def parse_element(elem):
            """Recursively parse XML element into Python data structure."""
            result = {}
            
            # group items by their tag to detect arrays
            tag_groups = {}
            for child in elem:
                if child.tag not in tag_groups:
                    tag_groups[child.tag] = []
                tag_groups[child.tag].append(child)
            
            # process each group of elements
            for tag, children in tag_groups.items():
                # skip empty elements
                if len(children) == 0:
                    continue

                # if we have multiple items or this is an array container
                if len(children) > 1 or any(c.tag == 'item' for c in children):
                    items = []
                    # process each child in the group
                    for child in children:
                        if child.tag == 'item':
                            # handle item elements
                            if len(child) > 0:
                                # complex item with children
                                items.append(parse_element(child))
                            else:
                                # simple item (primitive value)
                                items.append(child.text or '')
                        else:
                            # handle non-item array elements
                            if len(child) > 0:
                                items.append(parse_element(child))
                            else:
                                items.append(child.text or '')
                    result[tag] = items
                else:
                    # single element
                    child = children[0]
                    if len(child) > 0:
                        result[tag] = parse_element(child)
                    else:
                        result[tag] = child.text or ''
            
            return result

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            if root.tag == 'root':
                # handle standard format with record elements
                records = []
                for record in root.findall('record'):
                    records.append(parse_element(record))
                return records
            else:
                # handle single record or custom format
                return [parse_element(root)]
                
        except FileNotFoundError:
            raise ValueError(f"Input file not found: {xml_path}")
        except ET.ParseError:
            raise ValueError(f"Invalid XML format: {xml_path}")

    def write_xml(self, data, xml_path):
        """Write data to XML, preserving original structure and order."""
        def build_xml(element, value):
            if isinstance(value, dict):
                # Process dictionary items in original order
                for k, v in value.items():
                    # Skip null values but allow 0/False
                    if v is not None and (v or isinstance(v, (bool, int, float))):
                        child = ET.SubElement(element, k)
                        build_xml(child, v)
            elif isinstance(value, list):
                # For arrays, maintain the same tag for all items
                for item in value:
                    # For primitive arrays, create direct items
                    if isinstance(item, (str, int, float, bool)):
                        child = ET.SubElement(element, 'item')
                        child.text = str(item)
                    else:
                        # For object arrays, keep the parent tag's structure
                        child = ET.SubElement(element, 'item')
                        build_xml(child, item)
            else:
                # Handle primitive values
                element.text = str(value) if value is not None else ''

        try:
            root = ET.Element("root")
            if isinstance(data, list):
                # For list input, wrap each item in a record element
                for record in data:
                    record_elem = ET.SubElement(root, "record")
                    build_xml(record_elem, record)
            else:
                # For single record input
                build_xml(root, data)

            # Format the XML with proper indentation
            def indent(elem, level=0):
                i = "\n" + level * "  "
                if len(elem):
                    if not elem.text or not elem.text.strip():
                        elem.text = i + "  "
                    if not elem.tail or not elem.tail.strip():
                        elem.tail = i
                    for subelem in elem:
                        indent(subelem, level + 1)
                    if not elem.tail or not elem.tail.strip():
                        elem.tail = i
                else:
                    if level and (not elem.tail or not elem.tail.strip()):
                        elem.tail = i

            indent(root)
            tree = ET.ElementTree(root)
            # Use UTF-8 encoding and add XML declaration
            tree.write(xml_path, encoding='utf-8', xml_declaration=True)
            
            # Add final newline
            with open(xml_path, 'a') as f:
                f.write('\n')

        except IOError:
            raise ValueError(f"Unable to write to file: {xml_path}")
    
    # the idea is to generate random data based on regular expressions defined for each header in the config file
    def generate_data(self, rows, output_path, output_format):
        """Generate mock data based on configured header patterns."""
        logging.info(f"Starting data generation for {rows} rows")
        start_time = time.time()
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            headers = config['headers']
            patterns = config['patterns']
            # convert headers/patterns to compatible C types
            num_headers = len(headers)
            c_headers = (ctypes.c_char_p * num_headers)()
            c_patterns = (ctypes.c_char_p * num_headers)()
            for i, h in enumerate(headers):
                c_headers[i] = h.encode()
                c_patterns[i] = patterns[h].encode()

            # calling C function for random data generation
            row_ptr_type = ctypes.POINTER(ctypes.c_char_p)
            data_pointer = row_ptr_type()
            if self.lib.generate_all_data(
                    c_headers, c_patterns, num_headers,
                    rows, ctypes.byref(data_pointer)) != 0:
                raise RuntimeError("Data generation failed in C library.")

            # convert returned data to python structure
            data = []
            for i in range(rows):
                row_data = {}
                for j, header in enumerate(headers):
                    row_data[header] = data_pointer[i * num_headers + j].decode()
                data.append(row_data)

            # write output
            if output_format == 'csv':
                with open(output_path, 'w', newline='', buffering=8192) as csv_file:
                    writer = csv.DictWriter(csv_file, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(data)
            elif output_format == 'json':
                with open(output_path, 'w', buffering=8192) as json_file:
                    json.dump(data, json_file, indent=4)
            elif output_format == 'xml':
                self.write_xml(data, output_path)
            elif output_format == 'sqlite':
                self.write_sqlite(data, output_path, 'data')
            elapsed_time = (time.time() - start_time) * 1000
            logging.info(f"Data generation completed in {elapsed_time:.2f} ms")
        except Exception as e:
            logging.error(f"Error during data generation: {str(e)}")
            raise

    def convert(self, input_path, output_path, input_format, output_format, table=None, flatten=False):
        """Convert data from one format to another."""
        logging.info(f"Starting conversion from {input_format} to {output_format}")
        start_time = time.time()

        try:
            # read chosen input format
            if input_format == 'csv':
                data = self.read_csv(input_path)
            elif input_format == 'json':
                data = self.read_json(input_path)
            elif input_format == 'sqlite':
                data = self.read_sqlite(input_path, table)
                if isinstance(data, dict):  # Multiple tables
                    base_path = os.path.splitext(output_path)[0]
                    for table_name, table_data in data.items():
                        table_output = f"{base_path}_{table_name}.{output_format}"
                        self._write_output(table_data, table_output, output_format, flatten)
                    return
            elif input_format == 'xml':
                data = self.read_xml(input_path)
            else:
                raise ValueError(f"Unsupported input format: {input_format}")
            
            self._write_output(data, output_path, output_format, flatten)
            
            elapsed_time = (time.time() - start_time) * 1000
            logging.info(f"Conversion completed successfully in {elapsed_time:.2f} ms")
        
        except Warning as w:
            raise NestedDataWarning(str(w))
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            raise

    def _write_output(self, data, output_path, output_format, flatten=False):
        """Helper method to write output in specified format."""
        # check for nested structures in formats that may use them
        nest_formats = ['json', 'xml']
        structured_formats = ['csv', 'sqlite']
        if isinstance(data, list) and data and output_format in structured_formats:
            if self.is_nested(data):
                if flatten:
                    data = self.flatten_data(data)
                else:
                    raise Warning("Nested data detected in structured format output.")

        # write to chosen output format
        if output_format == 'csv':
            self.write_csv(data, output_path)
        elif output_format == 'json':
            self.write_json(data, output_path)
        elif output_format == 'sqlite':
            table_name = os.path.splitext(os.path.basename(output_path))[0]
            self.write_sqlite(data, output_path, table_name)
        elif output_format == 'xml':
            self.write_xml(data, output_path)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

class NestedDataWarning(Warning):
    pass

# can be used as a command line tool through this file, will have less functionality than the browser interface
class DataTransformerCLI:
    def __init__(self):
        self.transformer = DataTransformer()
        self.format_mapping = {
            '.csv': 'csv',
            '.json': 'json',
            '.sqlite': 'sqlite',
            '.xml': 'xml'
        }

    def run(self):
        parser = argparse.ArgumentParser(description='CLI tool for data transformation and mock data generation.')
        subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

        # convert command
        convert_parser = subparsers.add_parser('convert', aliases=['c'], help='Convert data from one format to another.')
        convert_parser.add_argument('input', help='Path to the input file.')
        convert_parser.add_argument('output', help='Path to the output file.')

        # generate command
        generate_parser = subparsers.add_parser('generate', aliases=['g'], help='Generate mock data.')
        generate_parser.add_argument('rows', type=int, help='Number of rows to generate.')
        generate_parser.add_argument('output', help='Path to the output file.')

        args = parser.parse_args()

        if args.command in ('convert', 'c'):
            self.handle_convert(args.input, args.output)
        elif args.command in ('generate', 'g'):
            self.handle_generate(args.rows, args.output)

    def handle_convert(self, input_path, output_path):
        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' does not exist.")
            return

        # determine given input and output formats
        input_ext = os.path.splitext(input_path)[1].lower()
        output_ext = os.path.splitext(output_path)[1].lower()

        input_format = self.format_mapping.get(input_ext)
        output_format = self.format_mapping.get(output_ext)

        if not input_format:
            print(f"Unsupported input format: {input_ext}")
            return
        if not output_format:
            print(f"Unsupported output format: {output_ext}")
            return

        try:
            # convert dataset
            self.transformer.convert(input_path, output_path, input_format, output_format,
                                  flatten=False)
            print(f"Successfully converted '{input_path}' to '{output_path}'.")
        except NestedDataWarning:
            # check for nested data, notify user
            response = input("Nested data detected. Flatten it for structured output? (y/n): ").strip().lower()
            if response == 'y':
                self.transformer.convert(input_path, output_path, input_format, output_format, flatten=True)
                print(f"Successfully converted '{input_path}' to '{output_path}' with flattening.")
            else:
                print("Conversion aborted by user.")
        except Exception as e:
            print(f"Conversion failed: {str(e)}")

    def handle_generate(self, rows, output_path):
        # determine output format
        output_ext = os.path.splitext(output_path)[1].lower()
        output_format = self.format_mapping.get(output_ext)

        if not output_format:
            print(f"Unsupported output format: {output_ext}")
            return

        try:
            self.transformer.generate_data(rows, output_path, output_format)
            print(f"Successfully generated {rows} rows into '{output_path}'.")
        except Exception as e:
            print(f"Data generation failed: {str(e)}")

UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'csv', 'json', 'sqlite', 'xml'}

class MultipartFormParser:
    """Parser for multipart/form-data"""
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
                if (input_format == 'sqlite'):
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
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "type": "success",
                    "message": "Conversion completed successfully"
                }).encode())

            except NestedDataWarning:
                self.send_response(200)  # Changed from 500 to 200
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "type": "nested_data_warning",
                    "message": "Nested data detected. Would you like to flatten it?"
                }).encode())
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

def run_server(port=8000):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    server = HTTPServer(('localhost', port), DataTransformerHandler)
    print(f'Starting server on http://localhost:{port}')
    server.serve_forever()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # web interface if "serve" argument is provided
        run_server()
    else:
        # CLI by default with command line arguments
        cli = DataTransformerCLI()
        cli.run()