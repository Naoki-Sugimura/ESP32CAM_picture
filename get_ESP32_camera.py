import cv2
import numpy as np

import requests
import sys

'''
INFO SECTION
- if you want to monitor raw parameters of ESP32CAM, open the browser and go to http://192.168.x.x/status
- command can be sent through an HTTP get composed in the following way http://192.168.x.x/control?var=VARIABLE_NAME&val=VALUE (check varname and value in status)
'''

class ESP32Getter():
    def __init__(self, url, type="rtsp") -> None:
        # ESP32 self.URL
        # self.URL = "http://192.168.43.101"
        self.url = url
        AWB = True
        if(type=="http"):
            self.cap = cv2.VideoCapture(f"http://{self.url}")
        elif(type=="rtsp"):
            self.cap = cv2.VideoCapture(f"rtsp://{self.url}:554/mjpeg/1")
        else:
            sys.exit()
        
        self.set_resolution(index=8)
        # self.set_resolution(index=idx, verbose=True)
        # self.set_quality(value=val)

    def set_resolution(self, index: int=1, verbose: bool=False):
        try:
            if verbose:
                resolutions = "10: UXGA(1600x1200)\n9: SXGA(1280x1024)\n8: XGA(1024x768)\n7: SVGA(800x600)\n6: VGA(640x480)\n5: CIF(400x296)\n4: QVGA(320x240)\n3: HQVGA(240x176)\n0: QQVGA(160x120)"
                print("available resolutions\n{}".format(resolutions))

            if index in [10, 9, 8, 7, 6, 5, 4, 3, 0]:
                requests.get(self.url + "/control?var=framesize&val={}".format(index))
            else:
                print("Wrong index")
        except:
            print("SET_RESOLUTION: something went wrong")

    def set_quality(self, value: int=1, verbose: bool=False):
        try:
            if value >= 10 and value <=63:
                requests.get(self.url + "/control?var=quality&val={}".format(value))
        except:
            print("SET_QUALITY: something went wrong")

    def set_awb(self, awb: int=1):
        try:
            awb = not awb
            requests.get(self.url + "/control?var=awb&val={}".format(1 if awb else 0))
        except:
            print("SET_QUALITY: something went wrong")
        return awb
    
    def get_frame(self):
        success, frame = self.cap.read()

        if success:
            return cv2.flip(frame, 0)
        else:
            return None
    
    def destroy(self):
        self.cap.release()
        cv2.destroyAllWindows()



if __name__ == '__main__':

    url1 = "192.168.137.50"
    esp1 = ESP32Getter(url1, type="rtsp")
    while True:
        frame = esp1.get_frame()

        if frame is not None:
            cv2.imshow("frame", frame)

        key = cv2.waitKey(1)

        if key == 27:
            break
    
    esp1.destroy()