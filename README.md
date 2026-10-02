# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Ayberkrk/timoshenko/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                           |    Stmts |     Miss |   Cover |   Missing |
|------------------------------- | -------: | -------: | ------: | --------: |
| src/timoshenko/\_\_init\_\_.py |       37 |        0 |    100% |           |
| src/timoshenko/\_validation.py |       12 |        1 |     92% |        18 |
| src/timoshenko/adapters.py     |       68 |       18 |     74% |49, 51, 53, 62, 65-71, 85-89, 96, 105 |
| src/timoshenko/assets.py       |       41 |        7 |     83% |19, 21, 28, 41, 43, 45, 52 |
| src/timoshenko/beams.py        |       37 |        0 |    100% |           |
| src/timoshenko/csv\_source.py  |      127 |       22 |     83% |26-27, 32, 41, 70, 75, 80, 82, 98, 101-102, 106-107, 109-110, 120-121, 128, 136-137, 142, 178 |
| src/timoshenko/health.py       |       66 |        5 |     92% |95, 97, 104, 106, 134 |
| src/timoshenko/mechanics.py    |       26 |        1 |     96% |        45 |
| src/timoshenko/modal.py        |      125 |        5 |     96% |71, 182, 184, 225, 229 |
| src/timoshenko/monitor.py      |       19 |        0 |    100% |           |
| src/timoshenko/mqtt.py         |      205 |       35 |     83% |66, 68, 70, 106, 108-112, 129, 131, 135, 139, 142-144, 156, 159-161, 168, 174, 178-179, 190, 192, 223, 227-228, 239, 242, 247, 257-258, 260 |
| src/timoshenko/multichannel.py |       76 |       15 |     80% |30, 35, 37, 39, 41, 43, 45, 47, 57, 61, 79, 82, 85, 92, 102 |
| src/timoshenko/observations.py |       58 |        5 |     91% |38, 40, 87-88, 91 |
| src/timoshenko/oma.py          |      131 |       11 |     92% |94, 128, 145, 230, 232, 234, 237, 239-240, 244, 254 |
| src/timoshenko/plugins.py      |       87 |       10 |     89% |45, 47, 76, 103, 116-119, 125, 128 |
| src/timoshenko/polygon.py      |      188 |       21 |     89% |90, 97, 114, 122, 124, 130, 145, 166, 170, 173, 189, 192, 198-199, 201, 203, 212, 214-215, 219, 221 |
| src/timoshenko/pressure.py     |       15 |        2 |     87% |    26, 28 |
| src/timoshenko/project.py      |      152 |       20 |     87% |93, 96, 102, 115, 118, 121, 124-125, 130, 136, 141, 146, 150, 155, 158, 163, 195, 224, 229, 233 |
| src/timoshenko/report.py       |       81 |        6 |     93% |14, 17, 28, 108, 117, 121 |
| src/timoshenko/sections.py     |       77 |        4 |     95% |85, 111, 130, 133 |
| src/timoshenko/sensors.py      |       93 |       20 |     78% |30, 32, 34, 37, 39, 41, 48, 68-70, 97, 102, 122, 130-133, 135, 139-141 |
| src/timoshenko/sensorthings.py |      179 |       33 |     82% |28, 31-32, 60-61, 70, 73, 77, 111, 115, 119, 121, 123, 126, 128, 131, 136, 140, 154, 160, 168, 171, 175, 210, 214-215, 217, 219, 224, 235, 239, 253-254 |
| src/timoshenko/session.py      |      247 |       22 |     91% |36, 68, 90, 130, 138, 140, 144, 146, 148, 150, 152, 196, 209, 222, 226, 239, 266, 316, 329, 334, 338, 351 |
| src/timoshenko/shafts.py       |       18 |        2 |     89% |    28, 30 |
| src/timoshenko/stability.py    |       14 |        2 |     86% |    18, 28 |
| src/timoshenko/storage.py      |      190 |       35 |     82% |34-35, 40, 77, 164, 177, 190, 202, 290, 297-298, 300-304, 306-310, 312, 316-319, 351, 384, 387, 410-419 |
| src/timoshenko/strength.py     |       17 |        1 |     94% |        25 |
| src/timoshenko/structural.py   |      646 |       80 |     88% |20, 93, 117, 148, 153, 155, 160, 180, 185-188, 191, 193, 219, 221, 223, 228, 230, 235, 242-245, 253, 257-259, 323, 335, 340, 380, 382, 384, 388, 393, 399-400, 411, 415-416, 425, 431, 470, 472, 474, 489, 502, 518, 529-530, 572, 574, 576, 580, 583, 587-588, 600-601, 609, 647, 651, 670, 688, 708, 737-739, 801-805, 834-839, 847 |
| src/timoshenko/structure.py    |       63 |        3 |     95% |42, 49, 53 |
| src/timoshenko/uncertainty.py  |      172 |        7 |     96% |111-112, 162, 167, 197-198, 212 |
| src/timoshenko/update.py       |       22 |        3 |     86% |24, 26, 37 |
| src/timoshenko/vibration.py    |       81 |        9 |     89% |22, 50, 54, 83, 92, 98, 116, 125, 128 |
| **TOTAL**                      | **3370** |  **405** | **88%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/Ayberkrk/timoshenko/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/Ayberkrk/timoshenko/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ayberkrk/timoshenko/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/Ayberkrk/timoshenko/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FAyberkrk%2Ftimoshenko%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/Ayberkrk/timoshenko/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.