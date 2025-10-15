import os
import csv
import json
import time
import ctypes
import sqlite3
import logging
import glob
import argparse
import xml.etree.ElementTree as ET

# -----------------------------------------------------------
#   
#   This python file is used as the main script,
#   it handles converting data between different formats
#   and includes generating mock data based on regex patterns.
#
#   Most of the mock data generation is written in randomvalues.c
#   which is compiled into a shared library and used through ctypes.
#
#------------------------------------------------------------

# ctypes structures for use with the C library 
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
    def __init__(self, config_path=None):
        self.supported_formats = ['csv', 'json', 'sqlite', 'xml']
        self.config_path = config_path or self._get_default_config_path()

        self.configs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'configs')
        os.makedirs(self.configs_dir, exist_ok=True)
        
        # C library and functions
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
        # the following C functions were only called for preview functionality
        # for actual data generation, the freeing should already be handled in C directly
        self.lib.free_ast.argtypes = [ctypes.POINTER(ASTNode)]
        self.lib.free_ast.restype = None
        self.lib.free_tokens.argtypes = [ctypes.POINTER(Token)]
        self.lib.free_tokens.restype = None

    def _get_default_config_path(self):
        """Get the default config path, create configs directory if needed."""
        configs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'configs')
        os.makedirs(configs_dir, exist_ok=True)
        
        default_path = os.path.join(configs_dir, 'default.json')
        if not os.path.exists(default_path):
            default_config = { # note: change to the better default config
                "headers": ["id", "name", "email"],
                "patterns": {
                    "id": "\\d{1,6}",
                    "name": "[A-Z][a-z]{2,10}",
                    "email": "[a-z]{3,8}@example\\.com"
                }
            }
            with open(default_path, 'w') as f:
                json.dump(default_config, f, indent=2)
        
        return default_path
    
    def list_config_files(self):
        """List all available configuration files in the configs directory."""
        configs = glob.glob(os.path.join(self.configs_dir, "*.json"))
        return [os.path.basename(c) for c in configs]
    
    def get_config(self, config_name=None):
        """Get configuration from a specific file or the current one."""
        if config_name:
            config_path = os.path.join(self.configs_dir, config_name)
        else:
            config_path = self.config_path
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logging.error(f"Error loading config {config_path}: {str(e)}")
            return None
    
    def save_config(self, config_data, config_name):
        """Save configuration to a file."""
        config_path = os.path.join(self.configs_dir, config_name)
        try:
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            self.config_path = config_path
            return True
        except Exception as e:
            logging.error(f"Error saving config {config_path}: {str(e)}")
            return False
    
    # can be removed, was only used for preview in browser
    def test_pattern(self, pattern, num_samples=5):
        """Test a regex pattern by generating mock samples for preview."""
                
        try:
            samples = []
            tokens_ptr = ctypes.POINTER(Token)()
            num_tokens = ctypes.c_int(0)
            pattern_bytes = pattern.encode('utf-8')
            
            if self.lib.tokenize(pattern_bytes, ctypes.byref(tokens_ptr), ctypes.byref(num_tokens)) != 0:
                return ["Error: Failed to tokenize pattern"]
                
            ast_ptr = ctypes.POINTER(ASTNode)()
            if self.lib.parse_tokens(tokens_ptr, num_tokens.value, ctypes.byref(ast_ptr)) != 0:
                self.lib.free_tokens(tokens_ptr)
                return ["Error: Failed to parse pattern"]
                
            buffer = ctypes.create_string_buffer(256)
            # generate samples
            for i in range(num_samples):
                if self.lib.generate_random_value_from_ast(ast_ptr, buffer, 255) != 0:
                    samples.append("Error generating sample")
                else:
                    sample_text = buffer.value.decode('utf-8', errors='replace')
                    samples.append(sample_text)
            
            self.lib.free_ast(ast_ptr)
            self.lib.free_tokens(tokens_ptr)
            
            return samples
            
        except Exception as e:
            logging.error(f"Error testing pattern: {str(e)}")
            return [str(e)]

    def is_semiStruct(self, data):
        """Check if data is semi-structured (has nested elements or irregular records)."""
        if not data:
            return False
            
        reference_keys = set(data[0].keys())
        
        for item in data:
            # check for structural irregularity by comparing keys to the first record
            if set(item.keys()) != reference_keys:
                return True
                
            # check for nested structures
            for value in item.values():
                if isinstance(value, (dict, list)):
                    return True
        
        return False
    
    # Logic for flattening semi-structured (nested or irregularly structured) data from JSON/XML.
    # JSON -> XML try to preserve the structure, since both can be semi-structured.
    # Essentially the structures are flattened so that every key is now represented in every record.
    # For nests, the parent key is prepended to the child key, and for arrays, the index is appended.
    def flatten_data(self, data):
        """Flatten semi-structured data into a structured format."""
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
        """Recursively flatten a single item."""
        flattened = {}
        for key, value in item.items():
            new_key = f"{parent_key}_{key}" if parent_key else key
            self._flatten_value(new_key, value, flattened)
        return flattened
    
    def _flatten_value(self, key, value, flattened):
        """Flatten a single value."""
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_value is not None:# preserve null values
                    self._flatten_value(f"{key}_{sub_key}", sub_value, flattened)
        elif isinstance(value, list):
            if value:   # process non-empty lists
                for idx, elem in enumerate(value):
                    if isinstance(elem, (dict, list)):
            # for nested structures (objects/arrays), use consistent indexing
                        self._flatten_value(f"{key}_{idx}", elem, flattened)
                    else:
            # for primitive arrays, use simpler indexing
                        flattened[f"{key}_{idx}"] = elem
        else:
            flattened[key] = value

    # Functions for reading and writing data sets in different formats:

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
                data = json.load(json_file)
                # for consistency across formats, we always return a list of records
                # so even if the input is a single record, we wrap it in a list
                if not isinstance(data, list):
                    data = [data]
                return data
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

    # listing tables to choose from in SQLite input files
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
    # note: change sqlite to limit to 1 table     
    def read_sqlite(self, db_path, table=None):
        """Read from SQLite, optionally from a specific table."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if table is None:
                tables = self.list_sqlite_tables(db_path)
                all_data = {}
                for t in tables:
                    cursor.execute(f'SELECT * FROM {t}')
                    headers = [desc[0] for desc in cursor.description]
                    all_data[t] = [dict(zip(headers, row)) for row in cursor.fetchall()]
                return all_data
            else:
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
        """Read XML"""
        def parse_element(elem):
            """Recursively parse XML element"""
        # special handling for array items
            if elem.tag == 'item':
        # if item has children, parse as object
                if len(elem) > 0:
                    return parse_element_content(elem)
        # otherwise treat as primitive value
                return elem.text or ''
            
            return parse_element_content(elem)
            
        def parse_element_content(elem):
            """Parse the actual content of an element."""
            result = {}
            
            # group by tag to detect arrays
            tag_groups = {}
            for child in elem:
                if child.tag not in tag_groups:
                    tag_groups[child.tag] = []
                tag_groups[child.tag].append(child)
            
            for tag, children in tag_groups.items():
                if len(children) == 0:
                    continue
                    
                # multiple elements with same tag -> array
                if len(children) > 1 or tag == 'item':
                    items = []
                    for child in children:
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
                records = []
                for record in root.findall('record'):
                    records.append(parse_element_content(record))
                return records
            return [parse_element_content(root)]
                
        except FileNotFoundError:
            raise ValueError(f"Input file not found: {xml_path}")
        except ET.ParseError:
            raise ValueError(f"Invalid XML format: {xml_path}")

    def write_xml(self, data, xml_path):
        """Write data to XML, preserving original structure and order when possible."""
        def build_xml(element, value):
            if isinstance(value, dict):
                # process dictionary items in original order
                for k, v in value.items():
                    # skip null values but allow 0/False
                    if v is not None and (v or isinstance(v, (bool, int, float))):
                        child = ET.SubElement(element, k)
                        build_xml(child, v)
            elif isinstance(value, list):
                # for arrays, maintain the same tag for all items
                for item in value:
                    # for primitive arrays, create direct items
                    if isinstance(item, (str, int, float, bool)):
                        child = ET.SubElement(element, 'item')
                        child.text = str(item)
                    else:
                        # for object arrays, keep the parent tag's structure
                        child = ET.SubElement(element, 'item')
                        build_xml(child, item)
            else:
                # handle primitive values
                element.text = str(value) if value is not None else ''

        try:
            root = ET.Element("root")
            if isinstance(data, list):
                # for list input, wrap each item in a record element
                for record in data:
                    record_elem = ET.SubElement(root, "record")
                    build_xml(record_elem, record)
            else:
                # for single record input
                build_xml(root, data)

            # format the XML with proper indentation
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
            tree.write(xml_path, encoding='utf-8', xml_declaration=True)
            
            with open(xml_path, 'a') as f:
                f.write('\n')

        except IOError:
            raise ValueError(f"Unable to write to file: {xml_path}")
    
    # generate random data based on regular expressions defined for each header/key in the config file
    def generate_data(self, rows, output_path, output_format):
        """Generate mock data based on configured patterns for each header."""
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

            # call C function for random data generation
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

    def _read_input(self, input_path, input_format, table=None):
        """Read input data based on format."""
        if input_format == 'csv':
            return self.read_csv(input_path)
        elif input_format == 'json':
            return self.read_json(input_path)
        elif input_format == 'sqlite':
            return self.read_sqlite(input_path, table)
        elif input_format == 'xml':
            return self.read_xml(input_path)
        else:
            raise ValueError(f"Unsupported input format: {input_format}")

    def convert(self, input_path, output_path, input_format, output_format, table=None, flatten=False):
        """Convert data from one format to another."""
        logging.info(f"Starting conversion from {input_format} to {output_format}")
        start_time = time.time()

        try:
            # read input data
            input_data = self._read_input(input_path, input_format, table)
            
            # handle tables from SQLite, currently allows choosing multiple in the UI(probably not needed)
            if isinstance(input_data, dict):
                base_path = os.path.splitext(output_path)[0]
                for table_name, table_data in input_data.items():
                    table_output = f"{base_path}_{table_name}.{output_format}"
                    self._write_output(table_data, table_output, output_format, flatten)
                
                elapsed_time = (time.time() - start_time) * 1000
                return {
                    'type': 'success',
                    'message': 'Multi-table conversion completed successfully',
                    'timing': {
                        'elapsed_ms': elapsed_time,
                        'rows_per_second': sum(len(td) for td in input_data.values()) / (elapsed_time / 1000)
                    }
                }
            
            # check for semi-structured data in input formats that may contain them if output is a structured format
            if isinstance(input_data, list) and input_data and output_format in ['csv', 'sqlite']:
                if self.is_semiStruct(input_data):
                    if flatten:
                        input_data = self.flatten_data(input_data)
                    else:
                        return {
                            'type': 'semi_data_warning',
                            'message': 'Irregular or nested data detected. Flatten it for structured output?'
                        }
            
            # write output
            self._write_output(input_data, output_path, output_format)
            
            elapsed_time = (time.time() - start_time) * 1000
            logging.info(f"Conversion completed in {elapsed_time:.2f} ms")
            
            return {
                'type': 'success',
                'message': 'Conversion completed successfully',
                'output_path': output_path,
                'timing': {
                    'elapsed_ms': elapsed_time,
                    'rows_per_second': len(input_data) / (elapsed_time / 1000)
                }
            }
            
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            raise

    def _write_output(self, data, output_path, output_format, flatten=False):
        """Write output in specified format."""
        # check structure

        structured_formats = ['csv', 'sqlite']
        if isinstance(data, list) and data and output_format in structured_formats:
            if self.is_semiStruct(data):
                if flatten:
                    data = self.flatten_data(data)
                else:
                    raise Warning("Irregular or nested data detected. Flatten it for structured output?")

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

# can be used as a command line tool through this file
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
        parser = argparse.ArgumentParser(
            prog='dsxform',
            description='CLI tool for data conversion and regex based mock data generation.',
            epilog=f'Supported formats: {self.transformer.supported_formats}'
        )
        subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

        # convert command
        convert_parser = subparsers.add_parser('convert', aliases=['c'], help='Convert data from one format to another.')
        convert_parser.add_argument('input', help='Path to the input file.')
        convert_parser.add_argument('output', help='Path to the output file.')

        # generate command
        generate_parser = subparsers.add_parser('generate', aliases=['g'], help='Generate mock data.')
        generate_parser.add_argument('rows', type=int, help='Number of rows to generate.')
        generate_parser.add_argument('output', help='Path to the output file.')
        generate_parser.add_argument('--config', '-C', help='Path to the configuration file. Uses default if not specified.')

        args = parser.parse_args()

        if args.command in ('convert', 'c'):
            self.handle_convert(args.input, args.output)
        elif args.command in ('generate', 'g'):
            self.handle_generate(args.rows, args.output, args.config)

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
            result = self.transformer.convert(input_path, output_path, input_format, output_format,
                                  flatten=False)
            if result['type'] == 'semi_data_warning':
                response = input("Irregular or nested data detected. Flatten it for structured output? y/n ").strip().lower()
                if response == 'y':
                    self.transformer.convert(input_path, output_path, input_format, output_format, flatten=True)
                    print(f"Successfully converted '{input_path}' to '{output_path}' with flattening.")
                else:
                    print("Conversion aborted by user.")
            else:
                print(f"Successfully converted '{input_path}' to '{output_path}'.")
        except Exception as e:
            print(f"Conversion failed: {str(e)}")

    def handle_generate(self, rows, output_path, config_path=None):
        # determine output format
        output_ext = os.path.splitext(output_path)[1].lower()
        output_format = self.format_mapping.get(output_ext)

        if not output_format:
            print(f"Unsupported output format: {output_ext}")
            return
        
        # set config path if provided
        if config_path:
            if not os.path.exists(config_path):
                print(f"Error: Config file '{config_path}' does not exist.")
                return
            self.transformer.config_path = config_path

        try:
            self.transformer.generate_data(rows, output_path, output_format)
            print(f"Successfully generated {rows} rows into '{output_path}'.")
        except Exception as e:
            print(f"Data generation failed: {str(e)}")

if __name__ == "__main__":
    cli = DataTransformerCLI()
    cli.run()