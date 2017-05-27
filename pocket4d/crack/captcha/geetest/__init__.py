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
    CONTOUR_MIN_X_OFFSET = 5

    CONTOUR_X_RANGE = 2

    def __init__(self, driver):
        self._driver = driver

        self._background = None
        self._mode = 0

        self._rect1_min_x = None
        self._rect1_max_x = None

    def _get_geetest_screen_element(self):
        return self._driver.find_element_by_class_name('gt_cut_fullbg')

    def _min_x(self, points):
        return min([p[0] for p in points])

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

        if self._mode == 0:
            if len(contours) != 2:
                return 0, False

            self._rect1_min_x = self._min_x(contours[1])
            self._rect1_max_x = self._max_x(contours[1])
            self._mode = 1

            return 1, True

        if self._mode == 1:
            if len(contours) > 2 or len(contours) == 0:
                return 0, False

            if len(contours) == 2:
                return 1, True

            if len(contours) == 1:
                min_x = self._min_x(contours[0])
                max_x = self._max_x(contours[0])

                if min_x + self.CONTOUR_MIN_X_OFFSET < self._rect1_min_x - self.CONTOUR_X_RANGE:
                    return 1, True

                if self._rect1_min_x - self.CONTOUR_X_RANGE <= min_x + self.CONTOUR_MIN_X_OFFSET <= self._rect1_min_x + self.CONTOUR_X_RANGE:
                    return 0, True

                if max_x > self._rect1_max_x:
                    return -1, True

                return 0, False

        return 0, False


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

            next_direction, ok = predictor.predict_direction()
            if not ok:
                ActionChains(driver).release(on_element=geetest_slider_element).perform()
                break

            if next_direction != current_direction:
                offset = int(offset/2.0)

            current_direction = next_direction

            if current_direction == 0 or offset == 0:
                ActionChains(driver).release(on_element=geetest_slider_element).perform()
                break

            xoffset = 20 + current_direction * offset + noise_offset()
            yoffset = 20 + noise_offset()
            ActionChains(driver).move_to_element_with_offset(to_element=geetest_slider_element, xoffset=xoffset, yoffset=yoffset).perform()

        try:
            ensure_geetest_crack_success(driver)
            cracked = True
            break
        except TimeoutException:
            reload_geetest_code(driver)
            continue

    return cracked
