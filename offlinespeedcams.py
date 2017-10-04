from __future__ import print_function, absolute_import

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


def igo2sygic(files, igo_types, dat_filename, debug):
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
            speedcam_csv = csv.reader(csvfile, delimiter=',', quotechar='"')

            for row in speedcam_csv:
                #omit header
                if speedcam_csv.line_num == 1 and row[0] == 'X':
                    continue

                #omit bad lines
                if len(row) != 6:
                    print(speedcam_csv.line_num, 'BAD LINE !!!', sep='; ')
                    continue

                latitude, longitude, speed, kind = row[1], row[0], row[3], row[2]

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

                #convert to sygic format
                speedcams.append([int(float(latitude) * 100000), int(float(longitude) * 100000), int(speed), int(kind)])

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

        latitude1, longitude1, speed1, _ = speedcams2.pop()

        location = str(latitude1) + ',' + str(longitude1)

        if location in radars:
            continue

        index2 = index1
        for speedcam2 in reversed(speedcams2):
            index2 -= 1
            latitude2, longitude2, speed2, _ = speedcam2

            if latitude1 == latitude2 and longitude1 == longitude2:
                if location not in radars:
                    radars[location] = [[index1, latitude1, longitude1, speed1, 0]]
                radars[location].append([index2, latitude2, longitude2, speed2, 0])
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

    print('\nSpeedCameras after cleaning: {:,}'.format(len(speedcams)))

    save_dat(speedcams, dat_filename, debug)


def save_dat(speedcams, dat_filename, debug):
    db_is_new = not os.path.exists(dat_filename)

    conn = sqlite3.connect(dat_filename, isolation_level=None)

    if db_is_new:
        db_schema = """
                    CREATE TABLE OfflineSpeedcam (Id INT NOT NULL, Latitude INT NOT NULL, Longitude INT NOT NULL, Type BYTE NOT NULL, Angle INT, BothWays BIT, SpeedLimit INT, Osm BIT);
                    CREATE INDEX speedcamsLatLon ON OfflineSpeedcam (Latitude, Longitude);
                    
                    CREATE TABLE OfflineZone (Id INT NOT NULL, Type BYTE NOT NULL, SpeedLimit SMALLINT NOT NULL, LatitudeMin INT NOT NULL, LongitudeMin INT NOT NULL, LatitudeMax INT NOT NULL, LongitudeMax INT NOT NULL);
                    CREATE INDEX zonesLatLon ON OfflineZone (LatitudeMin, LatitudeMax, LongitudeMin, LongitudeMax);
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
    sql = []
    for sc in speedcams:
        latitude, longitude, speed_limit, kind = sc

        if (latitude, longitude) not in offspeedcams:
            max_id += 1
            sql.append('insert into OfflineSpeedcam (Id, Latitude, Longitude, Type, Angle, BothWays, SpeedLimit, Osm) values ({Id}, {Latitude}, {Longitude}, {Type}, NULL, 1, {SpeedLimit}, 0);'.format(Id=max_id, Latitude=latitude, Longitude=longitude, SpeedLimit=speed_limit, Type=kind))
        else:
            if debug:
                print('Already exists in db', (latitude, longitude))

    if sql:
        conn.executescript('BEGIN TRANSACTION')
        conn.executescript(''.join(sql))
        conn.executescript('COMMIT')

    print('\nSpeedCameras added: {:,}'.format(len(sql)))


if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description='Sygic offlinespeedcams.dat generator. Convert Speed Camera / Photo Radar from IGO to Sygic', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('-t', '--type', choices=['igo'], default='igo', help='Input type')
    arg_parser.add_argument('-d', '--dat', '--destination', type=str, default='offlinespeedcams.dat', help='Destination DAT file')
    arg_parser.add_argument('-it', '--igotypes', action=type('', (argparse.Action,), dict(__call__=lambda self, parser, namespace, values, option_string: getattr(namespace, self.dest).update(dict([v.split('=') for v in values.replace(';', ',').split(',') if len(v.split('=')) == 2])))), default={}, metavar='KEY1=VAL1,KEY2=VAL2;KEY3=VAL3...', dest='igo_types', help='Default everything is 1 = speedcam. But you can specific your own type, first igo, second sygic: 1=1,2=1,3=2,4=3,5=9,6=4,7=9')
    arg_parser.add_argument('--debug', action='store_true', help='Print debug data')

    arg_parser.add_argument('files', nargs='*', help='Source files')

    args = arg_parser.parse_args()

    if args.type == 'igo':
        igo2sygic(args.files, args.igo_types, args.dat, args.debug)
