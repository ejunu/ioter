from common.utils import Utils
from common.device_command import CommandUtil

import os
import time
from enum import Enum
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtTest import *
from com.dtmilano.android.viewclient import ViewClient
# from com.dtmilano.android.adb.adbclient import AdbClient

ONBOARDING_TIMEOUT = 600
REMOVING_TIMEOUT = 120
# start onboarding
ONBOARDING_ADD_BUTTON = 0
ONBOARDING_ADDITIONAL_ADD_BUTTON = 1
ONBOARDING_MANUAL_PAIRING_CODE_BOTTON = 2
ONBOARDING_MANUAL_PAIRING_CODE_TEXTBOX = 3
ONBOARDING_MANUAL_PAIRING_CODE_INPUT_DONE = 4
ONBOARDING_CONTINUE_BUTTON = 5
ONBOARDING_NO_MATTER_CERT_DEVICE_SKIP_BUTTON = 6
ONBOARDING_MATTER_DEVICE_NAME_CHANGE = 7
ONBOARDING_MATTER_DEVICE_NAME_CHANGE_DONE = 8
ONBOARDING_DONE_BACK_TO_FIRST_SCREEN = 9
# remove device
REMOVE_START = 30
REMOVE_BUTTON = 31
REMOVE_DONE = 32
# error capture
ERROR_CHECK_LAYOUT = 40
# words
ERROR_OCCUR_KOR = 90
ERROR_OCCUR_ENG = 91
ADD_DEVICE_KOR = 92
ADD_DEVICE_ENG = 93
REMOVE_BUTTON_KOR = 94
REMOVE_BUTTON_ENG = 95


class STOnboardingResult():
    ONBOARDING_FAILURE = 0
    ONBOARDING_SUCCESS = 1
    REMOVING_FAILURE = 2
    REMOVING_SUCCESS = 3
    REMOVED_PHONE = 4


class AutoDeviceState():
    IDLE = 0
    CONNECTING_PHONE = 1
    ONBOARDING = 2
    REMOVING = 3


class simpleDlg(QDialog):
    def __init__(self, title, content):
        super(simpleDlg, self).__init__()
        self.app = QErrorMessage()
        self.app.showMessage(content)
        self.app.setWindowModality(Qt.WindowModal)
        self.app.setWindowTitle(title)
        self.app.exec()


class autoDevice(QThread):
    update_onboarding_state = pyqtSignal(int, str, str)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.device = None
        self.serialno = None
        self.vc = None
        self.running = False
        self.device_name = None
        self.comport = None
        self.device_num = None
        self.is_request = dict()
        self.debug = False
        # print("autoDevice")

    def run(self):
        self.running = True
        self.step = AutoDeviceState.IDLE
        self.is_request.clear()
        while self.running:
            if self.step == AutoDeviceState.CONNECTING_PHONE:
                if self.try_connect_phone():
                    self.step = AutoDeviceState.ONBOARDING
                    continue
                self.step = AutoDeviceState.IDLE
            elif self.step == AutoDeviceState.ONBOARDING:
                self.auto_onboarding_device()
                self.step = AutoDeviceState.IDLE
            elif self.step == AutoDeviceState.REMOVING:
                self.auto_remove_device()
                self.step = AutoDeviceState.IDLE
            QTest.qWait(1000)

    def get_number_of_adb_devices(self):
        sh_process = os.popen("adb devices")
        res = sh_process.read()
        list = res.split("\n")
        while "" in list:
            list.remove("")
        while "List of devices attached" in list:
            list.remove("List of devices attached")
        sh_process.close()
        return len(list)

    def check_connectable(self):
        adb_num = self.get_number_of_adb_devices()
        if adb_num > 0:
            os.system("adb root")
            return True
        else:
            return False

    def check_auto_available(self):
        if self.check_connectable():
            return True
        else:
            err = simpleDlg(
                "Error", "Can't work auto-onboarding because the phone is not connected")
            err.setWindowModality(Qt.NonModal)
            print("Can't work auto-onboarding because the phone is not connected")
            return False

    def is_running(self):
        return self.running

    def try_connect_phone(self):
        result = False
        if self.check_auto_available():
            try:
                (self.device, self.serialno) = ViewClient.connectToDeviceOrExit()
                self.vc = ViewClient(self.device, self.serialno)
                self.device.reconnect = True
            except RuntimeError as e:
                print("connect connect error", e)
            else:
                print("adb is connected")
                result = True
        return result

    def is_connected(self):
        if self.device and self.vc:
            return True
        else:
            return False

    def request_onboarding(self, comport, device_num, code, device_id):
        if self.step != AutoDeviceState.IDLE:
            print(f'working on something else  step : {self.step}')
            return False
        if True in self.is_request.values():
            print(f'working on something else is_request {self.is_request}')
            return False
        self.is_request[device_num] = True
        self.comport = comport
        self.device_num = device_num
        self.device_id = device_id
        self.pairing_code = code
        if not self.is_connected():
            self.step = AutoDeviceState.CONNECTING_PHONE
        else:
            self.step = AutoDeviceState.ONBOARDING
        return True

    def auto_onboarding_device(self):
        self.device_name = f"{CommandUtil.get_device_type_by_device_id(self.device_id)}-{self.device_num}"
        self.count = 0
        if self.auto_onboarding():
            print("onboarding success!")
            self.update_onboarding_state.emit(
                STOnboardingResult.ONBOARDING_SUCCESS, self.comport, self.device_num)
            self.is_request[self.device_num] = False
        else:
            print("onboarding failed..")
            self.update_onboarding_state.emit(
                STOnboardingResult.ONBOARDING_FAILURE, self.comport, self.device_num)
            if self.device_num in self.is_request:
                del self.is_request[self.device_num]

    def auto_onboarding(self):
        start_time = time.time()
        stair = ONBOARDING_ADD_BUTTON
        while self.running:
            # print(f"auto_onboarding step {self.step} device_num {self.device_num}")
            if True not in self.is_request.values():
                return False
            obj = self.get_obj(str(stair))
            if obj and stair == ONBOARDING_ADDITIONAL_ADD_BUTTON:
                if obj.getText() in [self.get_smartthings_view_id(ADD_DEVICE_KOR),
                                     self.get_smartthings_view_id(ADD_DEVICE_ENG)]:
                    if self.debug == True:
                        print(
                            f"stair::ONBOARDING_ADDITIONAL_ADD_BUTTON, obj={obj}")
                    obj.touch()
                    stair += 1
            elif not obj and stair == ONBOARDING_ADDITIONAL_ADD_BUTTON:
                obj = self.get_obj(str(stair), True)
                if obj:
                    if self.debug == True:
                        print(
                            f"stair::ONBOARDING_ADDITIONAL_ADD_BUTTON, obj={obj}")
                    obj.touch()
                    stair += 1
                else:
                    obj = self.get_obj(
                        str(ONBOARDING_MANUAL_PAIRING_CODE_BOTTON))
                    if obj:
                        if self.debug == True:
                            print(
                                f"stair::ONBOARDING_MANUAL_PAIRING_CODE_BOTTON, obj={obj}")
                        obj.touch()
                        stair += 2
            elif obj and stair == ONBOARDING_MANUAL_PAIRING_CODE_TEXTBOX:
                if self.debug == True:
                    print(
                        f"stair::ONBOARDING_MANUAL_PAIRING_CODE_TEXTBOX, obj={obj}")
                obj.type(self.pairing_code)
                stair += 1
            elif obj and stair == ONBOARDING_MATTER_DEVICE_NAME_CHANGE:
                if self.debug == True:
                    print(
                        f"stair::ONBOARDING_MATTER_DEVICE_NAME_CHANGE, obj={obj}")
                obj.setText(self.device_name)
                stair += 1
            elif obj and stair == ONBOARDING_MATTER_DEVICE_NAME_CHANGE_DONE:
                if self.debug == True:
                    print(
                        f"stair::ONBOARDING_MATTER_DEVICE_NAME_CHANGE_DONE, obj={obj}")
                if self.device.isKeyboardShown():
                    self.device.press("BACK")
                    if self.debug == True:
                        print(
                            f"stair::ONBOARDING_MATTER_DEVICE_NAME_CHANGE_DONE, keyboard down")
                    QTest.qWait(2000)
                obj.touch()
                QTest.qWait(12000)
                stair += 1
            elif stair == ONBOARDING_DONE_BACK_TO_FIRST_SCREEN:
                if self.debug == True:
                    print("stair::ONBOARDING_DONE_BACK_TO_FIRST_SCREEN")
                obj = self.get_obj("text:" + self.device_name, True)
                if obj or self.count >= 3:
                    if self.debug == True:
                        print(f"obj={obj}")
                    self.vc.device.press("BACK")
                    QTest.qWait(3000)
                    if self.debug == True:
                        print("press BACK")
                    return True
                else:
                    if self.debug == True:
                        print(
                            f"stair::ONBOARDING_DONE_BACK_TO_FIRST_SCREEN {self.device_name} not found")
                    self.count += 1
            elif obj:
                if self.debug == True:
                    print(f"stair::{stair}, obj={obj}")
                obj.touch()
                QTest.qWait(1000)
                stair += 1
            elif not obj:
                if stair == ONBOARDING_MATTER_DEVICE_NAME_CHANGE:
                    if self.debug == True:
                        print("waiting download plugin in SmartThings...")
                    self.view_dump(5)
                else:
                    if self.debug == True:
                        print(f"not found stair::{stair}'s obj")
                    self.view_dump()

            if True not in self.is_request.values():
                return False
            # screenshot when error occurs
            err = self.get_obj(str(ERROR_CHECK_LAYOUT))
            if err:
                if err.getText() in [self.get_smartthings_view_id(ERROR_OCCUR_KOR),
                                     self.get_smartthings_view_id(ERROR_OCCUR_ENG)]:
                    if self.debug == True:
                        print(err)
                    self.screenshot()
                    err2 = self.get_obj(
                        str(ONBOARDING_MATTER_DEVICE_NAME_CHANGE_DONE))
                    err2.touch()
                    QTest.qWait(1000)
                    self.vc.device.press("BACK")
                    if self.debug == True:
                        print("press BACK")
                    return False

            # screenshot when too much delay occurred during onboarding and return error
            now_time = time.time()
            if now_time - start_time > ONBOARDING_TIMEOUT:
                print(
                    f"Too much time {ONBOARDING_TIMEOUT}s goes on for onboarding... it is failed!")
                self.vc.device.press("BACK")
                while self.running:
                    ti = self.get_obj(str(ERROR_CHECK_LAYOUT), True)
                    if ti:
                        self.screenshot()
                        if self.debug == True:
                            print(ti)
                        ti.touch()
                        break
                QTest.qWait(1000)
                self.vc.device.press("BACK")
                QTest.qWait(1000)
                if self.debug == True:
                    print("press BACK")
                return False

    def disconnect_device(self, device_num):
        if device_num in self.is_request:
            del self.is_request[device_num]
            # self.step = 0

    def request_remove(self, comport, device_num, device_id):
        if self.step != AutoDeviceState.IDLE:
            print(f'working on something else  step : {self.is_request}')
            return
        if True in self.is_request.values():
            print(f'working on something else is_request : {self.is_request}')
            return
        if not device_num in self.is_request:
            return
        self.is_request[device_num] = True
        self.device_num = device_num
        self.comport = comport
        self.device_id = device_id
        self.step = AutoDeviceState.REMOVING

    def auto_remove_device(self):
        self.device_name = f"{CommandUtil.get_device_type_by_device_id(self.device_id)}-{self.device_num}"
        if self.remove_device():
            print("removing success!")
            self.update_onboarding_state.emit(
                STOnboardingResult.REMOVING_SUCCESS, self.comport, self.device_num)
            self.vc.sleep(1)
        else:
            print("removing failed!")
            self.update_onboarding_state.emit(
                STOnboardingResult.REMOVING_FAILURE, self.comport, self.device_num)
            self.vc.sleep(1)
        if self.device_num in self.is_request:
            del self.is_request[self.device_num]

    def remove_device(self):
        print(f"{self.device_name} will be removed ...")
        start_time = time.time()
        stair = REMOVE_START
        while self.running:
            if stair == REMOVE_START:
                obj = self.get_obj("text:" + self.device_name, True)
                if obj:
                    if self.debug == True:
                        print(obj)
                    (x, y) = obj.getCenter()
                    self.device.drag((x, y), (x, y), 2000, 1)
                    stair = stair + 1
                else:
                    print(f"can't find {self.device_name}")
                    if time.time() - start_time > REMOVING_TIMEOUT:
                        print(f"can't not find {self.device_name} anymore")
                        return False
                    continue
            elif stair >= REMOVE_BUTTON and stair <= REMOVE_DONE:
                self.view_dump()
                if stair == REMOVE_BUTTON:
                    obj = self.get_obj("text:" + str(REMOVE_BUTTON_KOR)
                                       ) or self.get_obj("text:" + str(REMOVE_BUTTON_ENG))
                else:
                    obj = self.get_obj(str(stair))
                if obj:
                    if self.debug == True:
                        print(obj)
                    obj.touch()
                    stair = stair + 1
                else:
                    if stair == REMOVE_BUTTON:
                        print(f"can't not find edit button")
                    elif stair == REMOVE_DONE:
                        print(f"can't find remove device button")
                    continue
            else:
                print("exit removing device")
                return True

    def screenshot(self):
        screenshot_path = Utils.get_screenshot_path()
        if not os.path.isdir(screenshot_path):
            os.mkdir(screenshot_path)
        self.view_dump()
        self.device.takeSnapshot(reconnect=True).save(
            f"{screenshot_path}error_{self.device_name}_{time.strftime('%Y_%m_%d-%H_%M_%S')}.png", "PNG")
        print("error screenshot done")

    def get_obj(self, key, request_dump=False):
        if not self.vc:
            return None
        if request_dump:
            self.view_dump()
        if key.startswith("text:"):
            text = key[len("text:"):]
            if text.isdecimal():
                return self.vc.findViewWithText(self.get_smartthings_view_id(int(text)))
            else:
                return self.vc.findViewWithText(text)
        else:
            return self.vc.findViewById(self.get_smartthings_view_id(int(key)))

    def view_dump(self, delay=1):
        try:
            self.vc.dump(window=-1, sleep=delay)
        except:
            pass

    def get_smartthings_view_id(self, key):
        type = {
            ONBOARDING_ADD_BUTTON: "com.samsung.android.oneconnect:id/add_menu_button",
            ONBOARDING_ADDITIONAL_ADD_BUTTON: "com.samsung.android.oneconnect:id/title",
            ONBOARDING_MANUAL_PAIRING_CODE_BOTTON: "com.samsung.android.oneconnect:id/enter_setup_code_button",
            ONBOARDING_MANUAL_PAIRING_CODE_TEXTBOX: "com.samsung.android.oneconnect:id/add_device_item_serial_edit_text",
            ONBOARDING_MANUAL_PAIRING_CODE_INPUT_DONE: "com.samsung.android.oneconnect:id/menu_done",
            ONBOARDING_CONTINUE_BUTTON: "com.samsung.android.oneconnect:id/onboarding_item_main_button",
            ONBOARDING_NO_MATTER_CERT_DEVICE_SKIP_BUTTON: "android:id/button1",
            ONBOARDING_MATTER_DEVICE_NAME_CHANGE: "com.samsung.android.oneconnect:id/onboarding_success_card_detail_view_editor",
            ONBOARDING_MATTER_DEVICE_NAME_CHANGE_DONE: "com.samsung.android.oneconnect:id/onboarding_item_positive_navigation_text",
            ONBOARDING_DONE_BACK_TO_FIRST_SCREEN: "android.widget.Button",\
            # REMOVE_BUTTON:"id/no_id/5",\
            REMOVE_BUTTON_ENG: "Remove",\
            REMOVE_DONE: "android:id/button1",\
            REMOVE_BUTTON_KOR: "삭제",\
            ERROR_CHECK_LAYOUT: "com.samsung.android.oneconnect:id/onboarding_step_description_layout",\
            ERROR_OCCUR_KOR: "오류가 있어요",\
            ERROR_OCCUR_ENG: "Something went wrong",\
            ADD_DEVICE_KOR: "기기 추가",\
            ADD_DEVICE_ENG: "Add device"
        }.get(key, key)
        return type

    def removed_phone(self):
        del self.device
        del self.vc
        self.device = None
        self.vc = None

    def stop(self):
        self.removed_phone()
        self.running = False
        self.is_request.clear()
        self.update_onboarding_state.emit(
            STOnboardingResult.REMOVED_PHONE, self.comport, self.device_num)
        self.quit()
        self.wait(1000)
