import random


class TextConversionManager:
    def __init__(self):
        self.random = random.Random()

    def spongebob_case(self, text: str) -> str:
        return "".join(self.random.choice([char.upper(), char.lower()]) for char in text)

    def zalgo_case(self, text: str) -> str:
        combining_chars = ["\u0305", "\u0332", "\u0338", "\u0320", "\u0311", "\u033f"]
        result = []
        for char in text:
            result.append(char)
            for _ in range(self.random.randint(2, 5)):
                result.append(self.random.choice(combining_chars))
        return "".join(result)

    def wide_case(self, text: str) -> str:
        return " ".join(char.upper() for char in text if char != " ")

    def glitch_void_case(self, text: str) -> str:
        glitch_chars = ["▰", "⚙", "", "█", "░", "▒", "⚔"]
        return "".join(
            self.random.choice(glitch_chars) if self.random.random() < 0.25 else char
            for char in text
        )

    def get_scary_text(self, text: str) -> str:
        chance = self.random.random()
        text = self.spongebob_case(text) if chance < 0.5 else self.wide_case(text)

        if self.random.random() < 0.7:
            text = self.glitch_void_case(text)

        if self.random.random() < 0.8:
            text = self.zalgo_case(text)

        return text
