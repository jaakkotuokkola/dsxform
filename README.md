# dsxform
A tool for regex-based mock data generation and dataset conversion. 

Supported formats: json, sqlite, csv, xml

## Features
  + ### Mock data generation:

    Create realistic mock data for testing and development using customizable regular expressions (regex). Outputs data as a flat dataset in your chosen format.
  + ### Dataset conversion:

    Convert datasets between the supported formats. Nested datasets are flattened when converted to CSV or SQLite.

## Interface
+ ### Web interface:

  Features previews of conversions and mock data generation. Includes an intuitive interface for creating and editing regex configurations for mock data.
+ ### CLI commands:

  For users preferring the command line, regex configurations can be created directly in a JSON file. Use the structure of default.json in the configs directory as a reference.
