"""
HIMAN - Human Behavior Simulator
Detection se bachne ke liye human-like actions
"""

import time
import random
import string
from loguru import logger


class HumanBehavior:
    """
    Saare actions human jaise karta hai
    - Random delays
    - Mouse movement simulation  
    - Typing speed variation
    - Random breaks
    """

    @staticmethod
    def random_delay(min_sec=1.5, max_sec=4.5):
        """Human jaise random wait karna"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    @staticmethod
    def typing_delay():
        """Typing ke beech human jaise pause"""
        time.sleep(random.uniform(0.05, 0.25))

    @staticmethod
    def page_load_wait():
        """Page load hone ka wait"""
        time.sleep(random.uniform(2.0, 5.0))

    @staticmethod
    def think_time():
        """Jaise human soch raha ho"""
        time.sleep(random.uniform(3.0, 8.0))

    @staticmethod
    def long_break():
        """Lamba break - jaise human kaam se uth gaya"""
        minutes = random.uniform(2, 8)
        logger.info(f"Human break: {minutes:.1f} minutes")
        time.sleep(minutes * 60)

    @staticmethod
    def human_type(element, text):
        """
        Human jaise type karna
        - Random speed
        - Kabhi kabhi galti bhi karta hai
        """
        element.clear()
        HumanBehavior.random_delay(0.3, 0.8)

        for char in text:
            element.send_keys(char)
            # Random typing speed
            time.sleep(random.uniform(0.05, 0.20))

            # 2% chance galti karna phir backspace
            if random.random() < 0.02 and len(text) > 3:
                wrong_char = random.choice(string.ascii_lowercase)
                element.send_keys(wrong_char)
                time.sleep(random.uniform(0.3, 0.8))
                element.send_keys('\b')  # backspace
                time.sleep(random.uniform(0.2, 0.5))

    @staticmethod
    def random_scroll(driver):
        """Random scroll karna - human jaise page padhna"""
        scroll_amount = random.randint(200, 600)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
        time.sleep(random.uniform(0.5, 1.5))

        # Kabhi kabhi wapas upar bhi scroll karo
        if random.random() < 0.3:
            driver.execute_script(f"window.scrollBy(0, -{random.randint(100, 300)})")
            time.sleep(random.uniform(0.3, 1.0))

    @staticmethod
    def working_hours_check():
        """
        Sirf working hours me kaam karo
        Raat ko zyada active nahi rehna (suspicious lagta hai)
        """
        from datetime import datetime
        hour = datetime.now().hour

        # Raat 2 baje se subah 7 baje tak slow karo
        if 2 <= hour <= 7:
            extra_delay = random.uniform(10, 30)
            logger.info(f"Late night mode - extra delay: {extra_delay:.0f}s")
            time.sleep(extra_delay)

    @staticmethod
    def get_random_user_agent():
        """Random browser identity"""
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        ]
        return random.choice(agents)

    @staticmethod
    def anti_detection_script():
        """
        Browser me inject karne ke liye script
        Automation detect hone se rokta hai
        """
        return """
        // WebDriver property hide karo
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Chrome automation flags remove karo
        window.chrome = {
            runtime: {}
        };
        
        // Permissions override
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
        """

    @staticmethod
    def session_time_limit():
        """
        Ek session me zyada der kaam mat karo
        Human jaise breaks lo
        Returns: True agar break lena chahiye
        """
        # 45-90 minute ke baad break
        session_duration = random.randint(45, 90)
        return session_duration
