# dsxform
A tool for regex-based data generation and dataset conversion.


  - Create syntatically realistic test data for quick testing and development using customizable regular expressions. Outputs data as a flat dataset in the chosen format.
    

  - Convert datasets between the supported formats (JSON, XML, SQLite & CSV). Nested datasets are flattened when converted to CSV or SQLite.

### CLI commands:
  Conversion:
  
  `~$ python transformdata.py convert <input_path> <output_path>`
  
  `~$ python transformdata.py c <input_path> <output_path>`
  
  Generation:
  
  `~$ python transformdata.py generate <number_of_rows> <output_path>`
  
  `~$ python transformdata.py g <number_of_rows> <output_path>`
  
  - Regex configurations can be created directly in a JSON file. Use the structure of default.json in the configs directory as a reference, since that is the structure they are read from.
  
  `~$ python transformdata.py generate <number_of_rows> <output_path> -C <config_path>`
  
 
  

