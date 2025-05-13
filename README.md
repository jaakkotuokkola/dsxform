# dsxform
A tool for regex-based mock data generation and dataset conversion. 

Supported formats: json, sqlite, csv, xml

note: Current repository may not work on Windows or macOS due to C shared library format (.so). 
Also requires Python installation on your OS. 
Templates folder or file dialog not needed if using only CLI interface.

## Features
  + ### Mock data generation:

    Create syntatically realistic mock data for testing and development using customizable regular expressions (regex). Outputs data as a flat dataset in your chosen format.
  + ### Dataset conversion:

    Convert datasets between the supported formats. Nested datasets are flattened when converted to CSV or SQLite.

## Interface
+ ### Browser interface:

  Features previews of conversions and mock data generation. Includes an intuitive interface for creating and editing the regex configurations.

  This can be started on localhost with the following command:

  `~$ python transformdata.py serve`
+ ### CLI commands:

  For users preferring the command line, regex configurations can be created directly in a JSON file. Use the structure of default.json in the configs directory as a reference. Currently transformdata.py works as the file the commands are used through.

  Conversion:
  
  `~$ python transformdata.py convert <input_path> <output_path>`
  
  `~$ python transformdata.py c <input_path> <output_path>`
  
  Generation:
  
  `~$ python transformdata.py generate <number_of_rows> <output_path>`
  
  `~$ python transformdata.py generate <number_of_rows> <output_path> -C <config_path>`
  
  `~$ python transformdata.py g <number_of_rows> <output_path>`
  

