# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Ayberkrk/timoshenko/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                             |    Stmts |     Miss |   Cover |   Missing |
|--------------------------------- | -------: | -------: | ------: | --------: |
| src/timoshenko/\_\_init\_\_.py   |       44 |        0 |    100% |           |
| src/timoshenko/\_spectral.py     |       22 |        4 |     82% |18, 23, 28, 31 |
| src/timoshenko/\_validation.py   |       12 |        0 |    100% |           |
| src/timoshenko/adapters.py       |       68 |        0 |    100% |           |
| src/timoshenko/alignment.py      |      162 |       17 |     90% |39, 41, 45, 78, 124, 128, 130, 133, 140, 147, 153, 164, 181, 190, 222-223, 233 |
| src/timoshenko/assets.py         |       41 |        7 |     83% |19, 21, 28, 49, 51, 53, 60 |
| src/timoshenko/beams.py          |       39 |        0 |    100% |           |
| src/timoshenko/csv\_source.py    |      125 |       21 |     83% |26-27, 32, 41, 70, 79, 83, 99, 102-103, 107-108, 110-111, 125-126, 133, 141-142, 151, 199 |
| src/timoshenko/dynamics.py       |      141 |       17 |     88% |63, 76, 106, 110, 113, 119, 126, 128, 131, 144, 148, 152, 156, 164-165, 183-184 |
| src/timoshenko/environmental.py  |       79 |       13 |     84% |41, 43, 45, 49, 51, 55, 57, 71, 75, 77, 113, 115, 117 |
| src/timoshenko/health.py         |       66 |        5 |     92% |95, 97, 104, 106, 136 |
| src/timoshenko/mechanics.py      |       26 |        1 |     96% |        45 |
| src/timoshenko/modal.py          |      128 |        5 |     96% |76, 214, 216, 265, 269 |
| src/timoshenko/model\_update.py  |       91 |       15 |     84% |58, 74, 77, 123-128, 139-145 |
| src/timoshenko/monitor.py        |       26 |        0 |    100% |           |
| src/timoshenko/mqtt.py           |      202 |       33 |     84% |73, 75, 77, 113, 115-121, 138, 140, 144, 148, 151-153, 165, 168-170, 177, 183, 191-194, 214, 218, 253, 257-258, 269, 272, 277, 288 |
| src/timoshenko/multichannel.py   |       80 |        0 |    100% |           |
| src/timoshenko/observations.py   |       58 |        5 |     91% |40, 42, 91-92, 95 |
| src/timoshenko/oma.py            |      175 |       19 |     89% |104, 108, 149, 166, 269, 284, 289, 299, 303, 310, 330, 332, 334, 339, 342, 344-345, 349, 361 |
| src/timoshenko/plugins.py        |       87 |       10 |     89% |45, 47, 78, 112, 127-130, 138, 141 |
| src/timoshenko/polygon.py        |      190 |       21 |     89% |107, 116, 133, 141, 143, 149, 164, 185, 189, 194, 208, 211, 217-218, 220, 222, 231, 233-234, 238, 240 |
| src/timoshenko/postgres.py       |      201 |       43 |     79% |46, 49, 53-54, 88, 181-182, 185, 189, 218, 229, 276, 357, 371, 379, 392-395, 406, 427, 437-459, 462-468, 473-490 |
| src/timoshenko/pressure.py       |       15 |        0 |    100% |           |
| src/timoshenko/project.py        |      152 |       20 |     87% |98, 101, 107, 120, 123, 126, 129-130, 135, 141, 146, 153, 157, 162, 165, 170, 202, 231, 236, 240 |
| src/timoshenko/report.py         |       81 |        6 |     93% |14, 21, 32, 120, 135, 139 |
| src/timoshenko/sections.py       |       79 |        4 |     95% |96, 122, 142, 147 |
| src/timoshenko/sensors.py        |       93 |        0 |    100% |           |
| src/timoshenko/sensorthings.py   |      179 |        2 |     99% |     68-69 |
| src/timoshenko/session.py        |      247 |       21 |     91% |36, 68, 90, 130, 142, 144, 150, 152, 154, 156, 160, 227, 240, 244, 257, 286, 340, 360, 365, 369, 388 |
| src/timoshenko/shafts.py         |       23 |        1 |     96% |        44 |
| src/timoshenko/ssi.py            |      188 |       18 |     90% |28, 62, 106, 111, 117, 123, 129, 131, 133, 135, 139, 144, 149, 151, 186, 219, 264, 321 |
| src/timoshenko/stability.py      |       17 |        0 |    100% |           |
| src/timoshenko/storage.py        |      210 |        1 |     99% |       544 |
| src/timoshenko/strength.py       |       20 |        0 |    100% |           |
| src/timoshenko/structural.py     |      962 |       89 |     91% |107, 158, 171-173, 241, 276, 289, 292, 296, 302, 322, 335, 339, 343, 369, 371, 375, 380, 382, 389, 400-405, 415, 423, 520, 537, 542, 585, 587, 591, 599, 601, 603, 605, 607, 610-611, 613, 620, 663, 666, 732, 785, 791, 795, 814-815, 838, 845-846, 857, 873, 927, 929, 940, 945-946, 956, 980, 1043, 1045, 1049, 1052, 1056-1057, 1072-1073, 1083, 1128, 1132, 1153, 1184, 1226, 1283, 1302, 1330, 1361-1363, 1484-1489, 1511, 1550 |
| src/timoshenko/structural\_3d.py |      353 |       43 |     88% |22, 53, 89, 93, 96, 100, 116, 123, 138, 142, 144, 149, 154, 158-160, 180, 191, 204, 220, 292, 300-301, 310, 360, 362, 364, 368-369, 383, 388-389, 395, 403, 417-418, 440, 449-452, 481-482 |
| src/timoshenko/structure.py      |       63 |        3 |     95% |44, 53, 59 |
| src/timoshenko/uncertainty.py    |      172 |        7 |     96% |127-128, 180, 185, 215-216, 232 |
| src/timoshenko/update.py         |       22 |        3 |     86% |24, 26, 41 |
| src/timoshenko/vibration.py      |       83 |        9 |     89% |22, 57, 61, 93, 102, 108, 132, 148, 151 |
| **TOTAL**                        | **5022** |  **463** | **91%** |           |


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