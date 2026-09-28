import time


class Show:
    WAIT_LIMIT = 15

    def __init__(self, app):
        self.app, self.pet, self.running = app, app.pet, True
        self._script = self._steps()
        self._next()

    def stop(self):
        if self.running:
            self.running, self.pet.run_target = False, None
            self.app.rouse(self.pet).finish_state()
            self.app.show_finished()

    def _next(self):
        if not self.running or self.app.quitting:
            return
        step = next(self._script, None)
        if step is None:
            self.running = False
            self.app.show_finished()
        elif callable(step):
            self._wait(step, time.time() + self.WAIT_LIMIT)
        else:
            self.app.root.after(int(step * 1000), self._next)

    def _wait(self, done, deadline):
        if self.running:
            if done() or time.time() > deadline:
                self._next()
            else:
                self.app.root.after(150, self._wait, done, deadline)

    def _steps(self):
        app = self.app
        pet = app.rouse(self.pet)
        spec, home = pet.spec, pet.cx
        app.react(pet, [("title", "Showtime!"), "Watch this..."], 2500, hop=1.2)
        yield 1.8
        area, reach = app.work_area_at(pet.cx, pet.cy), 520 * pet.unit
        left, right = max(area.left + pet.body_w, home - reach), min(area.right - pet.body_w, home + reach)
        for target, line in ((right if right - home > home - left else left, "Zoom!"), (home, "And back again!")):
            pet.say(line, 1500)
            pet.run_target = target
            yield lambda: pet.run_target is None
        app.react(pet, f"{spec.word} {spec.word}", 1600, hop=1.4)
        if spec.swims:
            app.bubbles(pet, 6)
        yield 1.8
        app.feed(force=True)
        yield lambda: app.treat is None
        yield 0.8
        app.on_pet_petted(pet)
        yield 2.2
        if pet.grounded:
            pet.airborne, pet.vx, pet.vy = True, 6 * pet.unit * pet.facing, -24 * pet.unit
            pet.set_state("fall")
            pet.say("Wheee!", 1500)
            yield lambda: not pet.airborne
        else:
            pet.set_state("alert", 1.6)
            pet.say("Bubble party!" if spec.swims else "Boing boing!", 1600)
            if spec.swims:
                app.bubbles(pet, 10)
            yield 1.8
        yield 0.6
        pet.sleep()
        pet.say("Zzz... (just kidding)", 2600)
        yield 3.0
        pet.wake(greet=False)
        app.stats_for(pet).add(happy=15)
        app.hearts(pet, 4)
        app.react(pet, [("title", "Ta-da!"), "Thank you, thank you!"], 3500, hop=1.4)
        yield 1.5
