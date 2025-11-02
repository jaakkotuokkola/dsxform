#### A tool for regex-based random data generation.

Creates random syntatically realistic data for quick testing using customizable regular expressions. Can also convert datasets between the supported formats (JSON, XML, SQLite & CSV). Nested datasets are flattened when converted to CSV or SQLite.

### CLI examples:
  
  Generates n rows of random data according to the specified regular expressions and headers in the config file. Outputs in the specified path and supported file format.
  
  - `~$ python transformdata.py generate <number_of_rows> <output_path>`
  
  - `~$ python transformdata.py g <number_of_rows> <output_path>`
  
  Regex configurations can be created directly in a JSON file and config path specified at the end with the -C parameter. Should use a structure similar to default.json, otherwise modify functions in transformdata.py.
  
  - `~$ python transformdata.py generate <number_of_rows> <output_path> -C <config_path>`
  
  Datasets can be converted between supported formats.
  
  - `~$ python transformdata.py convert <input_path> <output_path>`
  
  - `~$ python transformdata.py c <input_path> <output_path>`
  
  
 
  

