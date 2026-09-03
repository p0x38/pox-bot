# File structure

|Path|Description|
|:--|:--|
|src/assets/|an global resource folder for bot.|
|src/assets/voices/|an folder to store piper's voices. (need to download en_US-ryan-high.onnx and json in this folder, or you need to delete the code where using piper-tts)|
|data/|an data folder for bot.|
|logs/|an folder for logging.|
|conf/|an folder for configuring. (currently for logger)|
|cogs/|an folder for storing commands.|
|.env|a file for storing environment variables.|
|bot.py|a script for declaring `PoxBot` class.|
|ciphers.py|a script to storing cipher methods.|
|classes.py|a script to store custom classes.|
|data.py|a script to store custom data.|
|emoticons.txt|a text file for storing emoticons. and I forgot to place it at `src/assets/` :(|
|leaderboard.db|a SQLite database to store data such as leaderboard, points and etc.|
|logger.py|a script to declare logger.|
|main.py|a script to run bot.|
|pyproject.toml|a project file to make it work atleast.|
|requirements.txt|unused file to store required packages to install.|
|stuff.py|a script to store custom methods.|

## Other related links

- [User Data Structure](/user_directory_structure.md)