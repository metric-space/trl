import gc
import unittest

import numpy as np
import torch

from trl import DDPOConfig, DDPOTrainer, DefaultDDPOPipeline, DefaultDDPOScheduler


def scorer_function(images, prompts, metadata):
    return np.random.randint(6), {}


def prompt_function():
    return ("cabbages", {})


class DDPOTrainerTester(unittest.TestCase):
    """
    Test the DDPOTrainer class.
    """

    def setUp(self):
        self.ddpo_config = DDPOConfig(
            num_epochs=200,
            train_gradient_accumulation_steps=1,
            per_prompt_stat_tracking_buffer_size=32,
            sample_num_batches_per_epoch=2,
            sample_batch_size=2,
        )
        pretrained_model = "runwayml/stable-diffusion-v1-5"
        pretrained_revision = "main"

        pipeline = DefaultDDPOPipeline.from_pretrained(pretrained_model, revision=pretrained_revision)
        pipeline.scheduler = DefaultDDPOScheduler.from_config(pipeline.scheduler.config)

        self.trainer = DDPOTrainer(self.ddpo_config, scorer_function, prompt_function, pipeline)

        return super().setUp()

    def tearDown(self) -> None:
        gc.collect()

    def test_loss(self):
        advantage = torch.tensor([-1.0])
        clip_range = 0.0001
        ratio = torch.tensor([1.0])
        loss = self.trainer.loss(advantage, clip_range, ratio)
        self.assertEqual(loss.item(), 1.0)

    def test__generate_samples(self):
        samples, output_pairs = self.trainer._generate_samples(1, 2)
        self.assertEqual(len(samples), 1)
        self.assertEqual(len(output_pairs), 1)
        self.assertEqual(len(output_pairs[0][0]), 2)

    def test_calculate_loss(self):
        samples, _ = self.trainer._generate_samples(1, 2)
        sample = samples[0]

        latents = sample["latents"][0, 0].unsqueeze(0)
        next_latents = sample["next_latents"][0, 0].unsqueeze(0)
        log_probs = sample["log_probs"][0, 0].unsqueeze(0)
        timesteps = sample["timesteps"][0, 0].unsqueeze(0)
        prompt_embeds = sample["prompt_embeds"]
        advantage = torch.tensor([1.0], device=prompt_embeds.device)

        self.assertEqual(latents.shape, (1, 4, 64, 64))
        self.assertEqual(next_latents.shape, (1, 4, 64, 64))
        self.assertEqual(log_probs.shape, (1,))
        self.assertEqual(timesteps.shape, (1,))
        self.assertEqual(prompt_embeds.shape, (2, 77, 768))
        loss, approx_kl, clipfrac = self.trainer.calculate_loss(
            latents, timesteps, next_latents, log_probs, advantage, prompt_embeds
        )

        self.assertTrue(torch.isclose(loss.cpu(), torch.tensor([-1.0]), 1e-04))
