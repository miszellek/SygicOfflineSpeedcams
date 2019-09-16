# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import, unicode_literals

"""
Sygic OfflineSpeedCams generator. 
Convert Speed Camera / Photo Radar from IGO to Sygic.

Copyright (C) 2017 Miszel

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import csv
import sqlite3
import os
import re
import datetime


def igo2sygic(files, igo_types, debug):
    """
    SpeedCamText.txt

    header line: X, Y, TYPE, SPEED, DIRTYPE, DIRECTION

    X = longitude
    Y = latitude
    TYPE = type of speed camera ( 1 - fixed speed camera locations; 2 - combined red light and speed cameras; 3 - fixed red light camera locations; 4 - section camera positions; 5 - lasers, hand-held radars and other mobile speed camera locations; 6 - railway crossing; 7 - not constant mobile locations)
    SPEED = speed limit in km/h
    DIRTYPE = type of direction of the speedcam (0-all directions; 1-one direction; 2-both directions)
    DIRECTION = direction in degrees (0-North; 90-East)
    """

    speedcams = []  # [[latitude, longitude, speed, type], [...]]

    for filename in files:
        if not os.path.exists(filename):
            continue

        if debug:
            print('\n' + filename)

        with open(filename, 'rb') as csvfile:
            speedcam_csv = csv.reader(csvfile, delimiter=b',', quotechar=b'"')

            for row in speedcam_csv:
                #omit header
                if speedcam_csv.line_num == 1 and row[0] == 'X':
                    continue

                #omit bad lines
                if len(row) != 6:
                    if debug:
                        print(speedcam_csv.line_num, 'BAD LINE !!!', sep='; ')
                    continue

                longitude, latitude, kind, speed, dirtype, angle = row[0], row[1], row[2], row[3], row[4], row[5]

                #is latitude a float? if not, omit record
                try:
                    float(latitude)
                except ValueError:
                    if debug:
                        print(speedcam_csv.line_num, 'Y', latitude, sep='; ')
                    continue

                #is longitude a float? if not, omit record
                try:
                    float(longitude)
                except ValueError:
                    if debug:
                        print(speedcam_csv.line_num, 'X', longitude, sep='; ')
                    continue

                #is speed a integer? if not, try to find or set zero
                if not speed.isdigit():
                    #try to find first number in string
                    speed = re.search('\d+|$', speed).group()
                    if not speed.isdigit():
                        speed = 0
                    if debug:
                        print(speedcam_csv.line_num, 'SPEED', row[3], speed, sep='; ')

                if igo_types:
                    #is type a integer? if not, set as normal speed camera - 1
                    if not kind.isdigit():
                        kind = '1'
                        if debug:
                            print(speedcam_csv.line_num, 'TYPE', row[2], kind, sep='; ')

                    if kind in igo_types:
                        kind = igo_types[kind]
                    else:
                        if debug and igo_types:
                            print(speedcam_csv.line_num, 'TYPE', row[2], 'not defined in igotypes', sep='; ')
                        continue
                else:
                    kind = '1'

                #igo dirtype equals 0 or 2: both ways; dirtype equals 1: single direction
                both_ways = 0 if int(dirtype) == 1 else 1

                #convert to sygic format
                speedcams.append([int(float(latitude) * 100000), int(float(longitude) * 100000), int(speed), int(kind), int(angle), int(both_ways)])

    #sort by latitude, longitude, speed
    speedcams.sort(key=lambda x: (x[0], x[1], x[2]))

    print('\nSpeedCameras all: {:,}'.format(len(speedcams)))

    #eliminate duplicates:
    #append duplicated speed cameras to radars dict group by location
    radars = {}  #radars[location: latitude,longitude] = [[index, latitude, longitude, speed, mark_to_del: 0 - ok; 1 - del], [...], [...]]

    INDEX = 0
    SPEED = 3
    MARK = 4

    speedcams2 = speedcams[:]
    index1 = len(speedcams2)
    while speedcams2:
        index1 -= 1

        latitude1, longitude1, speed1, kind1, angle1, both_ways1 = speedcams2.pop()

        location = str(latitude1) + ',' + str(longitude1)

        if location in radars:
            continue

        index2 = index1
        for speedcam2 in reversed(speedcams2):
            index2 -= 1
            latitude2, longitude2, speed2, kind2, angle2, both_ways2 = speedcam2

            if latitude1 == latitude2 and longitude1 == longitude2:
                if location not in radars:
                    radars[location] = [[index1, latitude1, longitude1, speed1, kind1, angle1, both_ways1]]
                radars[location].append([index2, latitude2, longitude2, speed2, kind2, angle2, both_ways2])
            else:
                break

    #if exactly the same: leave first, mark rest to delete
    for duplicates in radars.values():
        for idx1 in range(len(duplicates)):
            for idx2, radar in enumerate(duplicates):
                if idx2 > idx1 and radar[SPEED] == duplicates[idx1][SPEED]:
                    radar[MARK] = 1

    def count2leave(duplicates):
        return sum(1 for radar in duplicates if radar[MARK] == 0)

    #one of speed is zero
    for duplicates in radars.values():
        if count2leave(duplicates) > 1:
            for radar in duplicates:
                if radar[SPEED] == 0:
                    radar[MARK] = 1

    #select lowest speed limit
    for duplicates in radars.values():
        if count2leave(duplicates) > 1:
            minspeed = min([radar[SPEED] for radar in duplicates if radar[MARK] == 0])
            for radar in duplicates:
                if radar[MARK] == 0 and radar[SPEED] != minspeed:
                    radar[MARK] = 1

    if debug:
        for location, duplicates in radars.items():
            print('\n', location, count2leave(duplicates))
            for radar in duplicates:
                print(radar)

    #delete marked
    del_list = [radar[INDEX] for duplicates in radars.values() for radar in duplicates if radar[MARK] == 1]
    del_list.sort(key=int, reverse=True)
    [speedcams.pop(d) for d in del_list]

    return speedcams


def dat2points(dat_filename):
    if not os.path.exists(dat_filename):
        return

    conn = sqlite3.connect(dat_filename, isolation_level=None)

    cursor = conn.cursor()

    cursor.execute('SELECT Latitude, Longitude, SpeedLimit, Type, Angle, BothWays FROM OfflineSpeedcam ORDER BY Latitude, Longitude')

    return cursor.fetchall()


def points2map(speedcams):
    html_filename = 'offlinespeedcams.dat_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    html = []
    html.append('<!DOCTYPE html>')
    html.append('<html>')
    html.append('<head>')
    html.append('    <title>' + html_filename + '</title>')
    html.append('    <meta charset="utf-8">')
    html.append('    <style>')
    html.append('        #map {')
    html.append('            height: 100%;')
    html.append('        }')
    html.append('')
    html.append('        html, body {')
    html.append('            height: 100%;')
    html.append('            margin: 0;')
    html.append('            padding: 0;')
    html.append('        }')
    html.append('    </style>')
    html.append('</head>')
    html.append('<body>')
    html.append('<div id="map"></div>')
    html.append('<script>')
    html.append('')
    html.append('    var sygicTypes = {')
    html.append('        0: {name: "RADAR_SYMBOL", symbol: "UE37A"},')
    html.append('        1: {name: "RADAR_STATIC_SPEED", symbol: "UE37B"},')
    html.append('        2: {name: "RADAR_STATIC_RED_LIGHT", symbol: "UE37E"},')
    html.append('        3: {name: "RADAR_SEMIMOBILE_SPEED", symbol: "UE37B"},')
    html.append('        4: {name: "RADAR_STATIC_AVERAGE_SPEED", symbol: "UE37C"},')
    html.append('        5: {name: "RADAR_MOBILE_SPEED", symbol: "UE37B"},')
    html.append('        6: {name: "RADAR_STATIC_RED_LIGHT_SPEED", symbol: "UE37E"},')
    html.append('        7: {name: "RADAR_MOBILE_RED_LIGHT", symbol: "UE37E"},')
    html.append('        8: {name: "RADAR_MOBILE_AVERAGE_SPEED", symbol: "UE37C"},')
    html.append('        9: {name: "RADAR_FAV_COPS_PLACE", symbol: "UE37D"},')
    html.append('        10: {name: "RADAR_INFO_CAMERA", symbol: "UE37A"},')
    html.append('        11: {name: "RADAR_DANGEROUS_PLACE", symbol: "UE37A"},')
    html.append('        12: {name: "RADAR_CONGESTION", symbol: "UE37F"},')
    html.append('        13: {name: "RADAR_WEIGHT_CHECK", symbol: "UE37A"},')
    html.append('        14: {name: "RADAR_DISTANCE_CHECK", symbol: "UE37A"},')
    html.append('        15: {name: "RADAR_CLOSURE", symbol: "UE030"},')
    html.append('        16: {name: "RADAR_SCHOOLZONE", symbol: "UE02E"}')
    html.append('    };')
    html.append('')
    html.append('')
    html.append(
        '    var UE37A = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAACc0lEQVRo3u1Z0XXCMAyUuwErZAVWYAVWYIV0BBghHSGMACOwQjoCjHD9wPQ58jmxHYLTV+49fkC2JVk6SUbkjTeWBwBbAC36qAGsSusWo3yDMK4ANqV1zFXexbq0rkz5HVG0CxjVLSqcAKxseLhonN8rq3QvJ0rr7RpQK+UuRGZNbqIqrfvDuxqbgOxeybWl9RdCl+2ALAu1cqwEYJMaFiTZu5IGXHISk6zblVDe82QsNZKbu76UVm0sd1O8SOrD/pUGjNJmxB4VSej5aTWGNkmM02Qljji9wgB99Q2RaYkBp8B+OhTno9VA8lVEjvU/bWDP7dhNDeEj0QZNkwdjzDeRY9/d2IbGmKOInJ2vqlg6TgISChCJbQwpRfIqmlajbsBu5nl/YMlNEmBv0d1vJSLPo9VUtgBvMXYja1ifNH3wCfD1emQNa51H2YWE6XRajaHNgDeRYrSzVteQ7RTltSejk4sYEFVlyZn53SqAUyyTkLW9ApV4bpN7rrvJpL5dhcI1ca1OaFowkzyYGovq9pLDAD7zjebe0OJkNsC9RajtJ2tgIU4cJwJwPi7yegC/now7Ek8aNOzhjzzI7m3gd7a7IeFs2lT7sJkhN4z0Xr3RVfdC2tsHY0xSX2PBQi6rLbB90qfa23cGibfsAhLIo+yKCn8G9yODxNqkycg65GQPm/xsAr8u1VrA9VjykD434PdXrYjNAUuT7pWccw6ZEzYX3Ulv/WuA+API4v6AsE52yeGmBbz3/RwKnUn5mlTlhgn9JWxE+nXgS/hrwhJxMMb4eYp71btMdc3M6BVbE4o5uSdy/jj3XDyi4xh4h3rjjX+LH/cFw6xmLw4KAAAAAElFTkSuQmCC";')
    html.append(
        '    var UE37B = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAACXklEQVRo3u2Y23niMBSEZ/ZLA26BFtgSSAlJCaQEXIIpAUqAEuwScAlQAi5h9sGSI/T5im3sZP2/cJPFGV3OGQlYmCmS1pJ2ku6alpOkbVWcrAh+AyCeehA9EpLvjQIkBQCuAAIAKYDzxIGvANgZCEnua1ubZSNJVyNmcpyYLv5vbzXPJSQz08EKwMeL485IHs371Lyuuwiw6gMAF+RL6qVIgiOilD8t+gmmCN7571raCJg1P15A4x7oQeh9/kDJJpybgBTAnmRZ7dibhBDhO6/3ZsgltCf5tyJ4AADJjOQXgHcA2ZwEhCTDto1JJkOJGELA2S/vkraSYseQ3U01LdIiyRTA1xwEPIy8pBjAAcDG+dqu/aukYiOb5ZZMKeBM8uYEf/IC9wkAxMaaWGor7dgCrEeB8ext/FKAfIYsvWagLI3aLNKm49R5v2nRvmgrKTBZKZN0Q26bSyGZSApRsunfShrfANR77nK6Fql1y0GycZXGNBcr8bRZ7CvAHfW047MpUNj1yQS4677LZiwOSxjQVpQiadVwa7Bx2sZq5u6mUXN0rWI39gwAwMGpsJ+oX0oZgE9bOyRFqMk+r5oBmerrPrOTdPHaRK6VMHajicYZGEqATMCtUqmkgy/OfL/W40XaSwVYDnL2hdNPoIqbPq9d1EXAGCeyLYCtF1fjIDmeqlNKHfNI2YVY0hGPt3CDCRjk5NTACrnd7gzbNFLuNCOMcz9Ud5I7OgVv4ffhpbxnufeJoa+V6HUcHLCP5zHV8/TEyF8HqbQjCvMZxTbP5US2CPixLAKmZhGw8L/zD2iHYmmrdwfBAAAAAElFTkSuQmCC";')
    html.append(
        '    var UE37C = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAACpElEQVRo3u1Z7ZHiMAyVbq4BKIErgRZyJbAlpAWuBLYEKAFKCCWwJSQlQAlvfyCBosuHw9ohd8ubYZixZVlPkWXZJnrhHwCADECB8bAFsIhl/EKUngDMRnDWEsAZQBlL4UoI5KmNN3NuZM7er/AjQF/N6/J5U2Ej01xCyYYQ8MgSOn85dMAjBCaFFAQuRPSHiOYsIKJf0jZ5AgdmnjPzOzPf4piZK2Z+J6I5ER2nSmDHzG9dAsx8YebfMUnEIlCRCREAOYDSZJcCgF38bzQg04xBYKchA2BLRFsisjk8I6JC9xKR3U2JwFGMz4moa8OzJUKUMAohcKTr5/5oE2Bm7QvZI1byX3XIVDJfb5j97BNg5oqu2SMEIRtRb3nAzAciOoRMGCWEAKjhHwHi6vko1WasNaChE+K1gxszLlx6VJRaavcUe7nIzKRk9iieRQCSPlWmcx8AsG/R8VQCNRId4/cd459OQMNp7cbMAKxd2JS4nvZmRuckCIRib3TquhlMoHcfSIiVLOoL3Te39MD9vJoCm69b+B3x4LrozVghiFqNDkRI2TEOJBWeHslAkwXqV5FRwqUJr2uVZyPlRnag++KuvqLohf8KLl3aGj+TtnPDmLX0laZtYdotboejFMYvu3ZTQ27l2jWlro0eLa1zpz/dUdN4bCMGnK23TL89nc0M4UUTodFgap4F7jW892AtjAypUwOh5E9W1vjMGaJPT4WTq4VRQ/ioHpgxNQyxa8hGdotrMUbvdTLnSb02WUnIaExHuQt9GGi+BoH1rsjpq+bZhE/R0O+zmG2PG1omXNQo/ek6ODl5DSMNn7ylv4Tc6jkCcd6IzYR6FeLTpl2QS9Pu87t/6fTp2CMegbZP3uDNTcuYfYveJf6+IyqF/HjZ6YXvjk9KkDD5QQnRFAAAAABJRU5ErkJggg==";')
    html.append(
        '    var UE37D = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAADIUlEQVRo3uVZ23XiMBC9k5MGSAluwSnBW4JTAlsClMCWQEqAEkwJUIIpwZRw84FsxrL8kmxDzt6fBCTNW6OZAfifQXJN8kByE0gnJ7khGS+tQME7DgE0Ij6wG3v+LVCHk/mbBNDQVr9MroCxUJuAJcNVgPv1uZNrA8nU2zwmxkly7yKs3L8OpH92rMUkz2Z9vJctAWliPlXrK/N97mslc3kb94jk3uKd+3ogVZe1xIFkVCrhRbjJZ6X45Q5+/nyMpQ/aGlMJ3mIwp8enIl54xeM4Pvtgq/96GGsnPXs2nAb5EK8afsO8otIXjUs31vquQ6A+xbOWc7G1LzZCa1n674RKjzb2ak/OdvgqsLNkKBx7aum26yX+ArAFcFPfHdX/N8wIEbmh/jKfjDz/RhMz1rBDKJ4o/ls9RzKh5ws/VKldmLwVps33AwQ/BArswpkefYWMFD4CkAGI1NcXPO7GVUSOA+jEeJTgEQAdJlcAXyIyurQeooBOZ5lRaCraMR+ZrZiSdslAP1reHVgPj5VS4hxO8UFYt32zFXKGV6J4BfXamqiuzWct5Bz8wkKJ9Rcxm1t4wzOo0beJ6dhfJlejVm4UQSGrcn6xlPCG7zrYcKwXdXsvIv4K6NBtDaM361CtkQaghb4uqYAp5sqCMWW9gq26wtpLbIRuww3AVkS+rTMp6i9zivqsx4VvyyBHEbladHcAutLoUUS+RB2IAPiNLp6Di4h86hDSLvsNaK+52N1tPRu1Cy0O4WMA09Uh0+MmIh/lB1dLaZcKVwCfIiIA/mCZbHQE8GF4/rXWugfJbDYrkbU+RyupkTtkssc36y4FdPyfB+wJmtSxOUDeOPbYRqvugSuExlZ/FxE5jTxTwdHBDal73HvongfZw6bEWg/qnhweGBJCWRfBRkyWShjhl0ixGR/j9rVjveoI3x063CwXRQDO7KwyJkcCoOjgWWVC1x3onSq8ACoZXQrY48RXw1aPXBoKWGXsyyP0d+Kn4z2cRDD0ZC/GvZ8IA5s/cdrYc4bZEO/TiL65a/+rz/uDVrZwmXlIZp8HOeRY80lTkcXwA9Aco7XKju/lAAAAAElFTkSuQmCC";')
    html.append(
        '    var UE37E = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAACQElEQVRo3u2a4XHiQAyFP91cA1wJbsFXApRgSvCVQEpISoASoARcAikhlBBKePeD9cDl7DXBWrOZyZvJ8EO7jN5Kq30SgW98YUgqJe01Ds+Pcr6Q9D7S+RaHe/34MYJDDcyczqOUVE9NoIzYdsDCrgA8AafInsLpMG5DJPdXkT0zSYeefet7/BgTgS68mNlLn9HMTsCSeCQeS2BogZkdgU2OBF7DCd+0NkcCn0mLLFPoMyXVq/y6Eigl3epYeeO6SQkArIYWSCo4P4J5Eoi9qCFCWzJNoRZrSVtJ/6RJIHbAMX0AfiYgAFABlaREX39BighMilQRgLN4u8Y8/LkiRQQa4FfQRO2DtTOzBWcdlAd61Ogh2KoO2z6o0S7b3WrUm8A84uA1wb0XAW8x1xB/zEpJFZmq0Tbfh+p8QaZi7iORSeAq5sJnM7DulUzF3CzIhVjzvgn3JFsx1w6pFvwfiScz+xMGWdNOILoQmUq8h0rTtWcdKbF3ldEUUmIGbCWduDT5rj1AagLXRJLPPVOr0R3DE7nHQPGpdN2xvgiNjusd8I7ACfgNNB8u7BtQmtkSRxkxCj0RqMNJv8Ui02N/eAROZrbhLOb66vxa56lElmKuHRdWA+sqMh0ttnAbmUxNoHV86HSPniS9R4sF8RH70cx2DKdZeijeE6+6bKFCufbE3lKilLQ1s6WkDRf9czSznaQ54Nq8p7jEVXi4aqAJ45UinPCe/vyfVm5IepYvkqjVGIEsfugeS+Lr/qvBN5zwF1uu96Vz+2R8AAAAAElFTkSuQmCC";')
    html.append(
        '    var UE37F = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAACh0lEQVRo3u1Y23GjQBDsuXICXAikwIWAQ5BDIAU5BCkEOwQRghSCFIIIQQ6h/cEsN2Bgd0ESdXV0lUrFY96zO70AK1asWLHif4b4XiC5AZDqrxh4rQLwCQAisl86KOv8B2t8aCBD721J7vTdK8lkad+dUxxzvEcmU5nD0s6nLvMzAs+WDGCyEyST2Mo9IoAryfMM+aetgRdj1O02lf6/T1UqIl/PCqAByRvbWK4FItDMAZLsPLsAKM11BqAvqC8AewAnEbksFgnJDach7+ixMyEWB5WPX0PG6EGvM9NWaYB8qov/Xsj9XptFjHrhAsAJAETkQvICIEfdJmPOJwCORkdDLQCUIlKNyOao2xNqyzl+JPknuC1JnjXyY08FesvdUz2S3EaXf7iS1xjB2PKnxqDDbo7zxpfM6AxLCP9O3xBsjZwjfOHZCvMnTi/J3OP0mZ3dgTVtcG1WBBkKD8BWdnAm/fLoqVBP5HcAbz0TNgeQoF7kJe4IXfhOp5+TaTbPnawXPe8VLiNm8Uaz1hCoLVf9rflNY7ocHnazdp4Re9mAvYZovkTqHIq8YM1EStQtZYfQ2FHUydi9vhKRUpMyNMyateg9E3cy4obOBiF9eX843lWJSBkdgAnkZrPwZLSms28X6nM+W9B5oNNW0QF0FFSaEQHwijZnOkkEALx17Oz1/m8oP1PMa10zIX/sPmxzougDkZG9de4n5llrMk+pwDPaZ4z9eqm9L0sHmw03VJSKWPYa9W3IDC2Hnd5PSB7tg7kBxJC+R6D1tWRKC5WeEj8ara8l0QEoyVoygNbpbkoF/n3wJ2u1mE0xOHyUvc3V7QwMnZfvwkp7djTqddCXihUrVqxYEYxvjk3SBt4cZTYAAAAASUVORK5CYII=";')
    html.append(
        '    var UE02E = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAAC7klEQVRo3u1Y3XnrIAyFbuAVvIJX8ApZIXcE3xHcEdIR3BGSEbyCM4I7wrkPhUYoAoTJT+/3RS+JAQkdJMQBY17ykpf812JrDQBojTE79/lhrf16Niit4x2AFaGsALpn+6YFcIQsh2f7pgWwRgAsj/TjrUK3KWz/dQDOhe2/DsBnpP39kQCqBMBQU4FcJRsADM8CsCcA5gK9BsDMNr9a/xaOdwAOUgVyK9pk9AfIstP6UON8bHK1MwkbY6k/RZvY0QZtvk6J3I5VqvuW4Eja5GQU7DQPTyEA7QbnvRwEeyMbs9579acKAJDSie2F4vwvcb4vXXHI6dYyu5QQrgD29wJw1HhNZCbAab3vFRGdOdBa5/lKxlhodLWJTq+M6KIF8ZZwvHUrScP61+hLHa0oX4k+SVrzXYazc4kA8F3OZmMM5TbvzrBWqO6Z/WrKZWeMKb8csZRZ8V0pWmwro42z6fO9AbArtKEneszJPgGsaHKv6/6PCr0R4V7TH3BugwWEDOVl1Mvq9L0zA/m/pICzObczVcivD0VRiOinSOGBRX37KY1r3l4cBVwuLhNpaxI6RyHy24ketuV/sNoRu1HQZIyPXt3h5lZxyboayoJEFcno+grmN33dtVMI+ZKIzIxM5cikEHA5tTvStp0rIbz//kwgTAIoXucEHS57MraPRaDkRhbkoLX2RD7PJqQLmteJnn3/ic1nrT1Za8XnmhIAtAoE3Ma9SNN3og7sIBSEgvy01n4YY06R/npBSKlnoZ9TjTFhi+d/69p5mt7uvQhhBRojY+imPiZsUT40MWD00Ftxq7uBtGLCmE4JgPIhzrk4bZlMrTCjh8zYWQHghw8p5gNqXytI/q/Iv7qNKQAsSql9QvfDkptX45BqJXAhaWukn96Fu4ytSQNWWqEB1ywym4su9Fc83m3OgRWCLMNkRUFXkRBnn0tGT6LHU64vY9MD1lMIXEiUj4JPoTWhE7vwSOeFt9sr7eUOxJe8pEb+ARnn4rUoLVH1AAAAAElFTkSuQmCC";')
    html.append('    var UE030 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QAAAAAAAD5Q7t/AAAB1UlEQVRo3u1Z25HCMAyUmWsgLdACLdBCWqCFtJAWaAFKgBKOEqCEUMLex5kZjyPbimPH8V32iwxE3pXWyA+iDRtmQaUIAmBPRK1+7B0/uxLRg4heSqlraeEf4h2AJ+LQAziUJJ4KF13BRYgfZ2Q8hK6mrLtwA9DkIH8WDN5rkXtHjA6yOfNMaqkA+W8Ap4iYh0DcNCI8thliiDuE3DzJibcTgHYpn3oSdYkN2Di8ek5JXJiw6ZV2+DMuG/NFDJMqDmDP+TE3eWN8zk7yHuHI/qItX0/g6VXQ3rfRC8ZMLYBzQbgKTPmm+S+tCNsJYRvjd2FVNPsGlwNThSb00lDS+wwfey6M/lJ3pmIiMhW+lVKPkgKI6G49j5YXO8+XdyoPO4EjR/gEvLiIyAeu49ocvBWw8S6XeDmHnSTKmvGnBRRpYAEOI0t9GZ/tCcP2AKVUkrMkIexJOxJgVkAkYGHYHPx9ienEx5LsmU7chl6w10LZdmAC8lFroVPtq9GGsVGJ/QCXfdmuDDXvyPTLde+JdZCeCVLHqYQOVPe5UCDg+k/mBIHXfzZqDFLv6bRQxAef+4HGEaPM/YBFIDfy3NAYIuq9I8tYjeVuKR1Cit4T/++b+g0J8AM1HTteeD/mQgAAAABJRU5ErkJggg==";')
    html.append('')
    html.append('    var map;')
    html.append('    var markers = [];')
    html.append('    var types = {};')
    html.append('')
    html.append('    function initMap() {')
    html.append('        map = new google.maps.Map(document.getElementById("map"), {')
    html.append('            zoom: 5,')
    html.append('            center: new google.maps.LatLng(48.208775, 16.372477)')
    html.append('        });')
    html.append('')
    html.append('        var speedCams = [')

    for sc in speedcams:
        latitude, longitude, speed_limit, kind, angle, both_ways = sc

        latitude = str(float(latitude) / 100000)
        longitude = str(float(longitude) / 100000)

        html.append('{y:' + latitude + ',x:' + longitude + ',s:' + str(speed_limit) + ',t:' + str(kind) + '},')

    html.append('        ];')
    html.append('')
    html.append('        speedCams.forEach(function (speedCam) {')
    html.append('')
    html.append('            types[speedCam.t] = (speedCam.t in types) ? types[speedCam.t] += 1 : 1;')
    html.append('')
    html.append('            markers.push(')
    html.append('                new google.maps.Marker({')
    html.append('                    map: map,')
    html.append('                    position: new google.maps.LatLng(speedCam.y, speedCam.x),')
    html.append('                    title: "SPEED: " + speedCam.t + "; TYPE: " + speedCam.t + ";",')
    html.append('                    type: speedCam.t,')
    html.append('                    visible: false')
    html.append('                }));')
    html.append('        });')
    html.append('')
    html.append('        function markersShowHide(type, visible) {')
    html.append('            console.log(type, visible);')
    html.append('            markers.forEach(function (marker) {')
    html.append('                if (marker.type == type) {')
    html.append('                    marker.setVisible(visible);')
    html.append('                }')
    html.append('            });')
    html.append('        }')
    html.append('')
    html.append('        var controlUI = document.createElement("div");')
    html.append('        controlUI.style.backgroundColor = "#fff";')
    html.append('        controlUI.style.border = "2px solid #fff";')
    html.append('        controlUI.style.borderRadius = "3px";')
    html.append('        controlUI.style.boxShadow = "0 2px 6px rgba(0,0,0,.3)";')
    html.append('        controlUI.style.lineHeight = "35px";')
    html.append('        controlUI.style.marginLeft = "10px";')
    html.append('        controlUI.style.textAlign = "left";')
    html.append('        controlUI.title = "Filter markers";')
    html.append('')
    html.append('        var centerControlDiv = document.createElement("div");')
    html.append('        centerControlDiv.index = 1;')
    html.append('        centerControlDiv.appendChild(controlUI);')
    html.append('')
    html.append('        for (var type in types) {')
    html.append('            var controlCheckBox = document.createElement("input");')
    html.append('            controlCheckBox.value = type;')
    html.append('            controlCheckBox.type = "checkbox";')
    html.append('            controlCheckBox.checked = false;')
    html.append('            controlCheckBox.style.margin = "0px 5px 0px 5px";')
    html.append('            controlCheckBox.style.verticalAlign = "middle";')
    html.append('')
    html.append('            controlCheckBox.addEventListener("click", function () {')
    html.append('                markersShowHide(this.value, this.checked);')
    html.append('            });')
    html.append('')
    html.append('            var controlImage = document.createElement("img");')
    html.append('            controlImage.src = (type in sygicTypes) ? eval(sygicTypes[type].symbol) : UE37A;')
    html.append('            controlImage.width = "24";')
    html.append('            controlImage.height = "24";')
    html.append('            controlImage.style.backgroundColor = "rgba(0,0,0,0.7)";')
    html.append('            controlImage.style.borderRadius = "10%";')
    html.append('            controlImage.style.margin = "0px 5px 0px 5px";')
    html.append('            controlImage.style.verticalAlign = "middle";')
    html.append('')
    html.append('            var controlText = document.createElement("span");')
    html.append('            controlText.style.color = "rgb(25,25,25)";')
    html.append('            controlText.style.fontFamily = "Roboto,Arial,sans-serif";')
    html.append('            controlText.style.fontSize = "11px";')
    html.append('            controlText.style.lineHeight = "38px";')
    html.append('            controlText.style.verticalAlign = "middle";')
    html.append('            controlText.innerHTML = type.toString() + " " + ((type in sygicTypes) ? sygicTypes[type].name : "") + " (" + types[type] + ")";')
    html.append('')
    html.append('            var controlHolder = document.createElement("div");')
    html.append('            controlHolder.style.paddingLeft = "5px";')
    html.append('            controlHolder.style.paddingRight = "5px";')
    html.append('            controlHolder.style.whiteSpace = "nowrap";')
    html.append('')
    html.append('            controlHolder.appendChild(controlCheckBox);')
    html.append('            controlHolder.appendChild(controlImage);')
    html.append('            controlHolder.appendChild(controlText);')
    html.append('')
    html.append('            controlUI.appendChild(controlHolder);')
    html.append('        }')
    html.append('')
    html.append('        map.controls[google.maps.ControlPosition.LEFT_CENTER].push(centerControlDiv);')
    html.append('    }')
    html.append('</script>')
    html.append('<script async defer src="https://maps.googleapis.com/maps/api/js?callback=initMap"></script>')
    html.append('</body>')
    html.append('</html>')

    with open(html_filename + '.html', 'w') as html_file:
        html_file.write('\n'.join(html))


def save_dat(speedcams, dat_filename, unit, debug):
    db_is_new = not os.path.exists(dat_filename)

    speed_limit_units = 1 if unit == 'mph' else 0

    conn = sqlite3.connect(dat_filename, isolation_level=None)

    if db_is_new:
        db_schema = """
                    CREATE TABLE Info (Version REAL not null, CreatedAt text not null, Note nvarchar(255) null);
                    CREATE TABLE OfflineSpeedcam (Id int not null, Latitude int not null, Longitude int not null, Type byte not null, Angle int null, BothWays bit, SpeedLimit int, Osm bit, PairId int null, SpeedLimitUnits byte null);
                    CREATE TABLE OfflineZone (Id int not null, Type byte not null, SpeedLimit smallint not null, LatitudeMin int not null, LongitudeMin int not null, LatitudeMax int not null, LongitudeMax int not null);

                    CREATE INDEX speedcamsLatLon ON OfflineSpeedcam (Latitude, Longitude);                    
                    """

        conn.executescript(db_schema)
        conn.commit()

    cursor = conn.cursor()

    #get max id
    cursor.execute('SELECT coalesce(max(Id), 0) AS max_id FROM OfflineSpeedcam')
    max_id = cursor.fetchone()[0]

    cursor.execute('SELECT Latitude, Longitude FROM OfflineSpeedcam ORDER BY Id')

    offspeedcams = cursor.fetchall()

    offspeedcams = set(offspeedcams)

    #generate SQL
    speedcams_added = []
    sql = []
    for sc in speedcams:
        latitude, longitude, speed_limit, kind, angle, both_ways = sc

        if (latitude, longitude) not in offspeedcams:
            max_id += 1
            sql.append('INSERT INTO OfflineSpeedcam (Id, Latitude, Longitude, Type, Angle, BothWays, SpeedLimit, Osm, PairId, SpeedLimitUnits) VALUES ({Id}, {Latitude}, {Longitude}, {Type}, {Angle}, {BothWays}, {SpeedLimit}, 0, NULL, {SpeedLimitUnits});'.format(Id=max_id, Latitude=latitude, Longitude=longitude, SpeedLimit=speed_limit, Type=kind, Angle=angle, BothWays=both_ways, SpeedLimitUnits=speed_limit_units))
            speedcams_added.append(sc)
        else:
            if debug:
                print('Already exists in db', (latitude, longitude))

    if sql:
        sql.append('DELETE FROM Info;')
        sql.append('INSERT INTO Info (Version, CreatedAt, Note) VALUES ({version}, "{createdAt}", NULL);'.format(version=2, createdAt=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.executescript('BEGIN TRANSACTION')
        conn.executescript(''.join(sql))
        conn.executescript('COMMIT')

    return speedcams_added


if __name__ == '__main__':
    import argparse
    import fnmatch
    import locale

    arg_parser = argparse.ArgumentParser(description='Sygic offlinespeedcams.dat generator. Convert Speed Camera / Photo Radar from IGO to Sygic', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('-t', '--type', choices=['igo'], default='igo', help='Input type')
    arg_parser.add_argument('-d', '--dat', type=str, default='offlinespeedcams.dat', help='DAT file')
    arg_parser.add_argument('-u', '--unit', choices=['kmh','mph'], default='kmh', help='Unit: kmh or mph')
    arg_parser.add_argument('-it', '--igotypes', action=type(b'', (argparse.Action,), dict(__call__=lambda self, parser, namespace, values, option_string: getattr(namespace, self.dest).update(dict([v.split('=') for v in values.replace(';', ',').split(',') if len(v.split('=')) == 2])))), default={'1':'1','2':'6','3':'2','4':'4','5':'5','6':'2','7':'2','8':'11','9':'16','10':'10','11':'6','12':'2','13':'10','15':'12','17':'9','31':'11'}, metavar='KEY1=VAL1,KEY2=VAL2;KEY3=VAL3...', dest='igo_types', help='You can specific your own types, first IGO, second Sygic')
    arg_parser.add_argument('--debug', action='store_true', help='Print debug data')
    arg_parser.add_argument('--map', action='store_true', default=True, help='Generate Google Maps with added points')
    arg_parser.add_argument('--dat2map', action='store_true', default=False, help='Generate Google Maps with points from offlinespeedcams.dat')

    arg_parser.add_argument('files', nargs='*', help='Source files')

    args = arg_parser.parse_args()


    def list_dir(cur_dir, mask, files_list):
        cur_dir = os.path.normpath(cur_dir)

        for f in os.listdir(cur_dir):
            file_name = os.path.normpath(os.path.join(cur_dir, f))
            if not f.startswith('.') and os.path.isdir(file_name):
                list_dir(file_name, mask, files_list)
            if f.startswith('.'):
                continue
            if fnmatch.fnmatch(f, mask) and os.path.isfile(file_name):
                files_list.append(file_name)


    all_files = []
    for filename in args.files:
        filename = os.path.abspath(os.path.normpath(unicode(filename, locale.getpreferredencoding())))

        if os.path.isfile(filename):
            all_files.append(filename)
        else:
            if os.path.isdir(filename):
                list_dir(os.path.dirname(filename), '*.*', all_files)
            else:
                list_dir(os.path.dirname(filename), os.path.basename(filename), all_files)

    if args.type == 'igo' and all_files:
        speedcams = igo2sygic(all_files, args.igo_types, args.debug)

        print('\nSpeedCameras after cleaning: {:,}'.format(len(speedcams)))

        speedcams_added = save_dat(speedcams, args.dat, args.unit, args.debug)

        print('\nSpeedCameras added: {:,}'.format(len(speedcams_added)))

        if args.map and speedcams_added:
            points2map(speedcams_added)

    if args.dat2map:
        dat_points = dat2points(args.dat)
        if dat_points:
            points2map(dat_points)
