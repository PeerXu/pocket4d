import time

import cStringIO
import numpy as np
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from .... import image as p4d_image


def shadow_filter(im_arr, in_of=25):
    im_arr = im_arr.astype(np.int16)
    b = 255/(255-in_of)
    im_arr = np.maximum(im_arr-in_of/b, 0)
    return im_arr.astype(np.uint8)


def ensure_geetest_code(driver):
    geetest_state_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'gt_ready')))
    return geetest_state_element


def ensure_geetest_code_crackable(driver):
    WebDriverWait(driver, 1).until_not(
        EC.presence_of_element_located((By.CLASS_NAME, 'gt_error')))


def ensure_geetest_crack_success(driver):
    WebDriverWait(driver, 2).until(
        EC.visibility_of_element_located((By.CLASS_NAME, 'gt_popup_finish')))

    WebDriverWait(driver, 5).until_not(
        EC.presence_of_element_located((By.CLASS_NAME, 'gt_popup_finish')))


def reload_geetest_code(driver):
    refresh_button_element = driver.find_element_by_class_name('gt_refresh_button')
    refresh_button_element.click()
    geetest_state_element = ensure_geetest_code(driver)
    ActionChains(driver).move_to_element(geetest_state_element).perform()


class GeetestRectPredictor(object):
    CONTOUR_MAX_X_OFFSET = 3

    CONTOUR_X_RANGE = 2

    def __init__(self, driver, max_switch_times=4, init_offset=None):
        self._driver = driver

        self._background = None
        self._mode = 0

        self._rect1_max_x = None
        self._max_switch_direction_times = max_switch_times * 2
        self._switch_direction_times = 0

        self._current_direction = 1
        self._current_offset = init_offset if init_offset else 30 + int(np.random.normal(20, 15))

    def _get_geetest_screen_element(self):
        return self._driver.find_element_by_class_name('gt_cut_fullbg')

    def _max_x(self, points):
        return max([p[0] for p in points])

    def capture_background(self):
        if self._background is None:
            f = cStringIO.StringIO(self._get_geetest_screen_element().screenshot_as_png)
            self._background = Image.open(f)

    def predict_direction(self):
        geetest_screen_snapshot = self._get_geetest_screen_element().screenshot_as_png
        im = Image.open(cStringIO.StringIO(geetest_screen_snapshot))
        diff_im = p4d_image.difference(self._background, im)
        diff_cv = np.array(diff_im)
        diff_cv = shadow_filter(diff_cv)
        contours = p4d_image.findContours(diff_cv)

        if len(contours) > 2:
            return 0, False

        if self._mode == 0:
            self._rect1_max_x = self._max_x(contours[-1])
            self._mode = 1

            return 1, True

        if self._mode == 1:
            max_x = self._max_x(contours[-1])
            if max_x > self._rect1_max_x + self.CONTOUR_MAX_X_OFFSET:
                return -1, True

            return 1, True

        return 0, False

    def next_step(self):
        next_direction, ok = self.predict_direction()
        if not ok:
            return (0, 0), False

        if next_direction != self._current_direction:
            self._switch_direction_times += 1
            self._current_direction = next_direction
            self._current_offset = self._current_offset / 2

            if self._current_offset == 0 or self._switch_direction_times == self._max_switch_direction_times:
                return (0, 0), True

        xoffset = 20 + self._current_direction * self._current_offset + noise_offset()
        yoffset = 20 + noise_offset()

        return (xoffset, yoffset), True


def noise_offset():
    return int(np.random.rand() * 10 - 3)


def crack(driver, init_offset=None):
    try:
        ensure_geetest_code(driver)
    except TimeoutException:
        return False

    while True:
        cracked = False

        try:
            ensure_geetest_code_crackable(driver)
        except TimeoutException:
            break

        predictor = GeetestRectPredictor(driver)
        predictor.capture_background()

        geetest_slider_element = driver.find_element_by_class_name('gt_slider_knob')
        ActionChains(driver).click_and_hold(on_element=geetest_slider_element).perform()
        time.sleep(0.3)

        current_direction = 1
        offset = init_offset if init_offset else 30 + int(np.random.normal(20, 15))

        start_at = time.time()
        while True:
            if time.time() - start_at > 15:
                break

            (xoffset, yoffset), ok = predictor.next_step()
            if not ok or xoffset == 0:
                ActionChains(driver).release(on_element=geetest_slider_element).perform()
                break

            ActionChains(driver).move_to_element_with_offset(to_element=geetest_slider_element, xoffset=xoffset, yoffset=yoffset).perform()
        try:
            ensure_geetest_crack_success(driver)
            cracked = True
            break
        except TimeoutException:
            reload_geetest_code(driver)
            continue

    return cracked
