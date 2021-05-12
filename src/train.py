from dataset import ClassificationDataLoader, ClassificationDataset, load_pickle_file
import config as cfg
import torch
from engine import Engine
from model import Model
import gc
import torch_xla.distributed.xla_multiprocessing as xmp

try:
    import torch_xla.core.xla_model as xm
    
    _xla_available = True
except:
    _xla_available = False


def train_model(tpu=False):
    train_ids = load_pickle_file(cfg.train_ids_224_pkl)
    train_class = load_pickle_file(cfg.train_class_224_pkl)
    train_images = load_pickle_file(cfg.train_image_224_pkl)

    val_ids = load_pickle_file(cfg.val_ids_224_pkl)
    val_class = load_pickle_file(cfg.val_class_224_pkl)
    val_images = load_pickle_file(cfg.val_image_224_pkl)

    if tpu == True:
        device = xm.xla_device()
    else:
        device = 'cuda'

    model = Model()
    model = model.to(device)

    train_dataset = ClassificationDataset(id=train_ids, classes = train_class, images = train_images)
    val_dataset = ClassificationDataset(id=val_ids, classes=val_class, images = val_images, is_valid=True)

    train_loader = ClassificationDataLoader(
        id = train_ids,
        classes = train_class,
        images = train_images
    ).fetch(
        batch_size=cfg.train_bs,
        drop_last = True,
        num_workers=0,
        shuffle=True,
        tpu = tpu
    )

    valid_loader = ClassificationDataLoader(
        id = val_ids,
        classes = val_class,
        images = val_images
    ).fetch(
        batch_size=cfg.val_bs,
        drop_last = False,
        num_workers=0,
        shuffle=True,
        tpu = tpu
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        patience=3,
        threshold=0.001,
        mode="min"
    )

    eng = Engine(model, optimizer, device=device, use_tpu=tpu, tpu_print = 10)

    for epoch in range(cfg.epochs):
        train_loss = eng.train(train_loader)
        valid_loss = eng.evaluate(valid_loader)
        xm.master_print(f"Epoch = {epoch}, LOSS = {valid_loss}")
        scheduler.step(valid_loss)
    gc.collect()



if __name__ == "__main__":

    def _mp_fn(rank, flags):
        torch.set_default_tensor_type('torch.FloatTensor')
        a = train_model(tpu=True)
    
    FLAGS = {}
    xmp.spawn(_mp_fn, args=(FLAGS,), nprocs=8, start_method='fork')
    # xmp.spawn(_mp_fn, args=(FLAGS,), nprocs=8, start_method='fork')