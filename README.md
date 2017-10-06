# Sygic OfflineSpeedcams

![Sygic 15.6.5+](https://img.shields.io/badge/sygic-15.6.5%2B-red.svg)
![Python 2.7+, 3.6+](https://img.shields.io/badge/python-2.7%2B%2C%203.6%2B-blue.svg)
[![MIT Licence](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Say Thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/miszellek)


Converter Speed Camera / Photo Radar from another formats (only from IGO at this time) to Sygic offlinespeedcams.dat


## Installing

### From the repository
```
git clone --recursive https://github.com/miszellek/SygicOfflineSpeedcams.git
```
### Directly from the GitHub 
```
wget https://raw.githubusercontent.com/miszellek/SygicOfflineSpeedcams/master/offlinespeedcams.py
```


## Usage

```
# basic example 
python offlinespeedcams.py speedcam_A.txt speedcam_AND.txt speedcam_B.txt speedcam_BG.txt speedcam_BiH.txt speedcam_BY.txt speedcam_CH.txt speedcam_CY.txt speedcam_CZ.txt speedcam_D.txt speedcam_DK.txt speedcam_E.txt speedcam_EST.txt speedcam_F.txt speedcam_FIN.txt speedcam_FL.txt speedcam_GB.txt speedcam_GR.txt speedcam_H.txt speedcam_HR.txt speedcam_I.txt speedcam_IRL.txt speedcam_IS.txt speedcam_KOS.txt speedcam_L.txt speedcam_LT.txt speedcam_LV.txt speedcam_M.txt speedcam_MA.txt speedcam_MK.txt speedcam_MNE.txt speedcam_N.txt speedcam_NL.txt speedcam_P.txt speedcam_PL.txt speedcam_RO.txt speedcam_RUS.txt speedcam_S.txt speedcam_SK.txt speedcam_SLO.txt speedcam_SRB.txt speedcam_TR.txt speedcam_UA.txt 

# with debug information 
python offlinespeedcams.py --debug SpeedCamText.txt

# 'type' translator
python offlinespeedcams.py --debug --igotypes 1=1,2=6,3=2,4=4,5=9,7=5 speedcam_EU.txt
```


## FAQ

**What for is a --igotypes switch?**

Hmm... difficult question... So...

Igo types of speed camera:
```
1 - fixed speed camera locations
2 - combined red light and speed cameras
3 - fixed red light camera locations 
4 - section camera positions
5 - lasers, hand-held radars and other mobile speed camera locations 
6 - railway crossing
7 - not constant mobile locations
```

Sygic types of speed camera:
```
0 - RADAR_SYMBOL
1 - RADAR_STATIC_SPEED
2 - RADAR_STATIC_RED_LIGHT
3 - RADAR_SEMIMOBILE_SPEED
4 - RADAR_STATIC_AVERAGE_SPEED
5 - RADAR_MOBILE_SPEED
6 - RADAR_STATIC_RED_LIGHT_SPEED
7 - RADAR_MOBILE_RED_LIGHT
8 - RADAR_MOBILE_AVERAGE_SPEED
9 - RADAR_FAV_COPS_PLACE
10 - RADAR_INFO_CAMERA
11 - RADAR_DANGEROUS_PLACE
12 - RADAR_CONGESTION
13 - RADAR_WEIGHT_CHECK
14 - RADAR_DISTANCE_CHECK
15 - RADAR_CLOSURE
16 - RADAR_SCHOOLZONE
```

In Sygic, column 'Type' in table 'OfflineSpeedcam' is equivalent to speedCamWarn{Type} in TTS info2.ini (Type: 9 = speedCamWarn9):
```
#I was try change it here
/Android/data/com.sygic.aura/files/Res/tts_info/TTS {YOUR LANGUAGE}/info2.ini
```
```
#but I had modify it inside the APK (and resign the apk after that):
\assets\Res\tts_info\TTS {YOUR LANGUAGE}/info2.ini
```

For example ENG TTS:
```
/Android/data/com.sygic.aura/files/Res/tts_info/TTS British English/info2.ini

[TRANSLATIONS]
...
speedCamWarn1=Speed camera is ahead.
speedCamWarn9=Police is ahead.
speedCamWarn16=Schoolzone is ahead.
speedCamWarn15=Closure is ahead.
speedCamWarn12=Traffic is ahead.
speedCamWarn11=Accident is ahead.
...
```

You can change it to:
```
speedCamWarn1=Speed camera is %DISTANCE% ahead.
speedCamWarn2=Red light camera is %DISTANCE% ahead.
speedCamWarn3=Semi mobile speed camera is %DISTANCE% ahead.
speedCamWarn4=Average speed camera is %DISTANCE% ahead.
speedCamWarn5=Mobile speed camera is %DISTANCE% ahead.
speedCamWarn6=Red light and speed camera is %DISTANCE% ahead.
speedCamWarn7=Mobile red light camera is %DISTANCE% ahead.
speedCamWarn8=Mobile average speed camera is %DISTANCE% ahead.
speedCamWarn9=Police is %DISTANCE% ahead.
speedCamWarn10=Different speed camera is %DISTANCE% ahead.
speedCamWarn11=Accident is %DISTANCE% ahead.
speedCamWarn12=Traffic is %DISTANCE% ahead.
speedCamWarn13=Weight check is %DISTANCE% ahead.
speedCamWarn14=Distance check is %DISTANCE% ahead.
speedCamWarn15=Closure is %DISTANCE% ahead.
speedCamWarn16=School zone is %DISTANCE% ahead.
```

And convert points like this:
```
# import all types speed camera, but omit railway crossing (6)
python offlinespeedcams.py --igotypes 1=1,2=6,3=2,4=4,5=9,7=5 SpeedCamText.txt
```

Of Course you can, not modify info2.ini, but you only hear "Speed camera is ahead", for every type.

PS:
Type 3 - RADAR_SEMIMOBILE_SPEED only show icon, no sound

**What with Angle, BothWays and Osm?**

I did not want to risk that something will not show up, so: 
* Angle is always Null = all directions (360)
* BothWays is always 1 = true
* Osm is always 0 = false, because i don't know what for it is ...

**I can't hear the speed of speed camera**

At this moment (v 17.2.11) Sygic cannot speak maximum speed of speed camera ;( maybe in future...

**What when I not use origin offlinespeedcams.dat from Sygic?**

The script will create empty database, but table OfflineZone will be empty ;( and you loose 'sygic' records from OfflineSpeedcam.   


## Contributing

### Bug Reports and Feature Requests

Please use [issue tracker](https://github.com/miszellek/SygicOfflineSpeedcams/issues) for reporting bugs or feature requests.

### Development

Pull requests are most welcome.


## License

MIT © Miszel


## Buy the developer a beer!

If you found my work helpful you can buy me a beer using

[![Donate](https://www.paypalobjects.com/webstatic/en_US/i/btn/png/silver-pill-paypal-44px.png)](https://www.paypal.com/paypalme/miszel/1EUR)
