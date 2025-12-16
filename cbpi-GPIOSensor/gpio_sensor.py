from cbpi.api import *
import RPi.GPIO as GPIO
import asyncio
import time


@cbpi.sensor
class GPIOSensor(CBPiSensor):
    """
    GPIO Sensor with different actions
    """

    ACTION_NEXT_STEP = "next_step"
    ACTION_ADD_TIMER = "add_timer"
    ACTION_EMERGENCY = "emergency"
    ACTION_TOGGLE_ACTOR = "toggle_actor"

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)

        self.gpio = int(props.get("gpio", 17))
        self.action = props.get("action")
        self.actor_id = props.get("actor")
        self.bounce_time = int(props.get("bounce", 300))

        self._last_trigger = 0

    async def on_start(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.add_event_detect(
            self.gpio,
            GPIO.FALLING,
            callback=self._gpio_callback,
            bouncetime=self.bounce_time
        )

        self.cbpi.notify(
            "GPIO Sensor",
            f"Sensor activ on GPIO {self.gpio}",
            NotificationType.INFO
        )

    def _gpio_callback(self, channel):
        now = time.time()
        if now - self._last_trigger < (self.bounce_time / 1000):
            return

        self._last_trigger = now

        asyncio.run_coroutine_threadsafe(
            self._handle_action(),
            self.cbpi.loop
        )

    async def _handle_action(self):

        # NEXT MASH STEP
        if self.action == self.ACTION_NEXT_STEP:
            try:
                await self.cbpi.step.next()
                self.cbpi.notify("GPIO Sensor", "Next Mash Step", NotificationType.INFO)
            except Exception:
                pass

        # +5 MIN TIMER
        elif self.action == self.ACTION_ADD_TIMER:
            try:
                step = self.cbpi.step.get_current()
                if step and step.timer:
                    step.timer.add(300)
                    self.cbpi.notify("GPIO Sensor", "+5 Minute Timer", NotificationType.INFO)
            except Exception:
                pass

        # Emergency stop
        elif self.action == self.ACTION_EMERGENCY:
            for actor in self.cbpi.actor.get_all():
                try:
                    await actor.instance.off()
                except Exception:
                    pass

            self.cbpi.notify("GPIO Sensor", "Emergency Stop triggered!", NotificationType.WARNING)

        # Toggle actuator
        elif self.action == self.ACTION_TOGGLE_ACTOR:
            if not self.actor_id:
                return

            actor = self.cbpi.actor.find_by_id(self.actor_id)
            if not actor:
                return

            if actor.instance.state:
                await actor.instance.off()
            else:
                await actor.instance.on()

            self.cbpi.notify(
                "GPIO Sensor",
                f"Actuator '{actor.name}' toggled",
                NotificationType.INFO
            )

    async def on_stop(self):
        GPIO.remove_event_detect(self.gpio)
        GPIO.cleanup(self.gpio)

    @classmethod
    def parameters(cls):
        return [
            Property.Number(
                "gpio",
                label="GPIO (BCM)",
                default=17
            ),
            Property.Select(
                "action",
                label="Aktion",
                options=[
                    {"label": "Next Mash Step", "value": cls.ACTION_NEXT_STEP},
                    {"label": "Add 5 min Timer", "value": cls.ACTION_ADD_TIMER},
                    {"label": "Emergency Stop", "value": cls.ACTION_EMERGENCY},
                    {"label": "Toggle Actuator", "value": cls.ACTION_TOGGLE_ACTOR},
                ],
                default=cls.ACTION_TOGGLE_ACTOR
            ),
            Property.Actor(
                "actor",
                label="Actuator (only for toggle)",
                description="Only required for 'Toggle Actuator'"
            ),
            Property.Number(
                "bounce",
                label="Debounce time (ms)",
                default=300
            )
        ]
