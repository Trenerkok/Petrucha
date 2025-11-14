import logging
from typing import Optional

import numpy as np
import sounddevice as sd

LOGGER = logging.getLogger(__name__)


class VADUtteranceRecorder:
    """
    Простий VAD-записувач фрази:
    - читає аудіо блоками (наприклад, по 100 мс),
    - чекає, поки кілька блоків поспіль будуть "гучними" -> початок фрази,
    - записує всі наступні блоки,
    - зупиняється, коли достатньо довго тихо -> кінець фрази,
    - повертає один np.ndarray (float32, mono) з усією фразою.
    """

    def __init__(
        self,
        samplerate: int = 16000,
        block_duration: float = 0.1,      # 100 мс блок
        energy_threshold: float = 0.02,   # поріг гучності (RMS)
        min_voice_blocks: int = 3,        # мін. к-сть "гучних" блоків для старту
        max_silence_blocks: int = 7,      # к-сть "тихих" блоків для стопу
        max_utterance_duration: float = 10.0,  # сек; захист від зависання
    ) -> None:
        self.samplerate = samplerate
        self.block_duration = block_duration
        self.block_size = int(samplerate * block_duration)
        self.energy_threshold = energy_threshold
        self.min_voice_blocks = min_voice_blocks
        self.max_silence_blocks = max_silence_blocks
        self.max_utterance_duration = max_utterance_duration

    def _compute_rms(self, block: np.ndarray) -> float:
        """RMS енергія блока."""
        if block.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(block.astype("float32") ** 2)))

    def record_utterance(self) -> np.ndarray:
        """
        Записати одну фразу:
        - чекаємо голос,
        - записуємо, поки не стане тихо достатньо довго,
        - повертаємо склеєний масив float32 (mono).
        Якщо голос так і не з'явився, повертаємо пустий масив.
        """
        LOGGER.info(
            "VAD: очікую фразу (sr=%d, block_size=%d, thr=%.4f)",
            self.samplerate,
            self.block_size,
            self.energy_threshold,
        )

        collected_blocks = []
        voice_blocks = 0
        silence_blocks = 0
        started = False

        max_blocks_total = int(self.max_utterance_duration / self.block_duration)

        with sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype="float32",
            blocksize=self.block_size,
        ) as stream:
            while True:
                frames, overflowed = stream.read(self.block_size)
                if overflowed:
                    LOGGER.warning("VAD: overflowed audio buffer")

                block = frames.reshape(-1).astype("float32")
                rms = self._compute_rms(block)

                if rms > self.energy_threshold:
                    voice_blocks += 1
                    silence_blocks = 0
                else:
                    silence_blocks += 1
                    voice_blocks = 0

                if not started:
                    if voice_blocks >= self.min_voice_blocks:
                        started = True
                        LOGGER.info(
                            "VAD: початок фрази (rms=%.4f, voice_blocks=%d)",
                            rms,
                            voice_blocks,
                        )
                        collected_blocks.append(block)
                else:
                    collected_blocks.append(block)

                    if silence_blocks >= self.max_silence_blocks:
                        LOGGER.info(
                            "VAD: кінець фрази (silence_blocks=%d)", silence_blocks
                        )
                        break

                    if len(collected_blocks) >= max_blocks_total:
                        LOGGER.info(
                            "VAD: досягнуто максимальну тривалість фрази (%d blocks)",
                            len(collected_blocks),
                        )
                        break

        if not collected_blocks:
            LOGGER.info("VAD: фразу не зафіксовано, повертаю пустий масив.")
            return np.zeros(0, dtype="float32")

        utterance = np.concatenate(collected_blocks).astype("float32")
        LOGGER.info("VAD: записано %d семплів у фразі.", utterance.shape[0])
        return utterance