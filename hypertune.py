from src.data import make_dataset
from src.models import rnn_models, metrics, train_model
from src.settings import SearchSpace, TrainerSettings, ReportTypes
from pathlib import Path
from ray.tune import JupyterNotebookReporter
from ray import tune
import torch
import ray
from typing import Dict
from ray.tune import CLIReporter
from ray.tune.schedulers import AsyncHyperBandScheduler
from ray.tune.schedulers.hb_bohb import HyperBandForBOHB
from ray.tune.search.bohb import TuneBOHB
from loguru import logger
from filelock import FileLock


def train(config: Dict, checkpoint_dir=None):
    """
    The train function should receive a config file, which is a Dict
    ray will modify the values inside the config before it is passed to the train
    function.
    """
    from mads_datasets import DatasetFactoryProvider, DatasetType

    # we lock the datadir to avoid parallel instances trying to
    # access the datadir
    data_dir = config["data_dir"]
    gesturesdatasetfactory = DatasetFactoryProvider.create_factory(DatasetType.GESTURES)
    with FileLock(data_dir / ".lock"):
        streamers = gesturesdatasetfactory.create_datastreamer(batchsize=32)
        train = streamers["train"]
        valid = streamers["valid"]

    # we set up the metric
    # and create the model with the config
    accuracy = metrics.Accuracy()
    model = rnn_models.GRUmodel(config)

    trainersettings = TrainerSettings(
        epochs=50,
        metrics=[accuracy],
        logdir=Path("."),
        train_steps=len(train),  # type: ignore
        valid_steps=len(valid),  # type: ignore
        reporttypes=[ReportTypes.RAY],
        scheduler_kwargs={"factor": 0.5, "patience": 5},
        earlystop_kwargs=None,
    )
    # because we set reporttypes=[ReportTypes.RAY]
    # the trainloop wont try to report back to tensorboard,
    # but will report back with tune.report
    # this way, ray will know whats going on,
    # and can start/pause/stop a loop.
    # This is why we set earlystop_kwargs=None, because we
    # are handing over this control to ray.

    trainer = train_model.Trainer(
        model=model,
        settings=trainersettings,
        loss_fn=torch.nn.CrossEntropyLoss(),
        optimizer=torch.optim.Adam,  # type: ignore
        traindataloader=train.stream(),
        validdataloader=valid.stream(),
        scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau,
    )

    trainer.loop()


if __name__ == "__main__":
    ray.init()

    # have a look in src.settings to see how SearchSpace is created.
    # If you want to search other ranges, you change this in the settings file.
    config = SearchSpace(
        input_size=3,
        output_size=20,
        tune_dir=Path("models/ray").resolve(),
        data_dir=Path("data/raw/gestures/gestures-dataset").resolve(),
    )

    reporter = CLIReporter()
    reporter.add_metric_column("Accuracy")

    bohb_hyperband = HyperBandForBOHB(
        time_attr="training_iteration",
        max_t=50,
        reduction_factor=3,
        stop_last_trials=False,
    )

    bohb_search = TuneBOHB()

    analysis = tune.run(
        train,
        config=config.dict(),
        metric="test_loss",
        mode="min",
        progress_reporter=reporter,
        local_dir=config.tune_dir,
        num_samples=50,
        search_alg=bohb_search,
        scheduler=bohb_hyperband,
        verbose=1,
    )

    ray.shutdown()
