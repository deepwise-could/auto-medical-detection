
import torch
from utils.files_utils import *
import importlib
import pkgutil
from training.trainer.Trainer import Trainer


def recursive_find_trainer(folder, trainer_name, current_module):
    tr = None
    for importer, modname, ispkg in pkgutil.iter_modules(folder):
        # print(modname, ispkg)
        if not ispkg:
            m = importlib.import_module(current_module + "." + modname)
            if hasattr(m, trainer_name):
                tr = getattr(m, trainer_name)
                break

    if tr is None:
        for importer, modname, ispkg in pkgutil.iter_modules(folder):
            if ispkg:
                next_current_module = current_module + "." + modname
                tr = recursive_find_trainer([join(folder[0], modname)], trainer_name, current_module=next_current_module)
            if tr is not None:
                break

    return tr


def search_and_load_model(pkl_file, checkpoint=None, train=False):
    """
    Load any trainer from a pkl. It will recursively search trainig.Trainer. 
    If checkpoint is specified, it will furthermore load the checkpoint file.
    The pkl file will be saved automatically when calling Trainer.store_checkpoint.
    :param pkl_file:
    :param checkpoint:
    :param train:
    :return:
    """
    info = load_pickle(pkl_file)
    init = info['init']
    name = info['name']
    search_in = join(UNet.__path__[0], "training", "net_training")
    tr = recursive_find_trainer([search_in], name, current_module="training.trainer")
    if tr is None:
        raise RuntimeError("Could not find the model trainer specified in checkpoint in trainig.trainer. "
                           "\nDebug info: \ncheckpoint file: %s\nName of trainer: %s " % (checkpoint, name))
                           
    assert issubclass(tr, Trainer), "The net trainer was found but is not a subclass of Trainer. " 
    
    if len(init) == 7:
        print("warning: this model seems to have been saved with a previous version. Attempting to load it anyways.")

        init = [init[i] for i in range(len(init)) if i != 2]

    # init[0] is the plans file. This argument needs to be replaced because the original plans file may not exist
    # anymore.
    trainer = tr(*init)
    trainer.process_plans(info['plans'])
    if checkpoint is not None:
        trainer.load_checkpoint(checkpoint, train)
    return trainer


def load_best_model_for_inference(folder):
    checkpoint = join(folder, "model_best.model")
    pkl_file = checkpoint + ".pkl"
    return search_and_load_model(pkl_file, checkpoint, False)


def load_model_and_checkpoint_files(folder, folds=None):
    """
    used for ensemble the five models of a cross-validation. This will restore the model from the
    checkpoint in fold 0, load all parameters of the five folds in ram and return both. 
    This will allow for fast switching between parameters

    used for inference and test prediction
    :param folder:
    :return:
    """
    if isinstance(folds, str):
        folds = [join(folder, "all")]
        assert isdir(folds[0]), "no output folder for fold %s found" % folds
    elif isinstance(folds, (list, tuple)):
        if len(folds) == 1 and folds[0] == "all":
            folds = [join(folder, "all")]
        else:
            folds = [join(folder, "fold_%d" % i) for i in folds]
        assert all([isdir(i) for i in folds]), "list of folds specified but not all output folders are present"
    elif isinstance(folds, int):
        folds = [join(folder, "fold_%d" % folds)]
        assert all([isdir(i) for i in folds]), "output folder missing for fold %d" % folds
    elif folds is None:
        print("folds is None so we will automatically look for output folders (not using \'all\'!)")
        folds = subfolders(folder, prefix="fold")
        print("found the following folds: ", folds)
    else:
        raise ValueError("Unknown value for folds. Type: %s. Expected: list of int, int, str or None", str(type(folds)))

    trainer = search_and_load_model(join(folds[0], "model_best.model.pkl"))
    trainer.output_folder = folder
    trainer.output_folder_base = folder
    trainer.update_fold(0)
    trainer.initialize(False)
    all_best_model_files = [join(i, "model_best.model") for i in folds]
    print("using the following model files: ", all_best_model_files)
    all_params = [torch.load(i, map_location=torch.device('cuda', torch.cuda.current_device())) for i in all_best_model_files]
    return trainer, all_params


if __name__ == "__main__":
    pkl = "/home/simon/med/results/UNetV2/UNetV2_3D_fullres/Task_Hippocampus/fold0/model_best.model.pkl"
    checkpoint = pkl[:-4]
    train = False
    trainer = search_and_load_model(pkl, checkpoint, train)
