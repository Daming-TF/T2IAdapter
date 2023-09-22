import numpy as np
from tqdm import tqdm
from PIL import Image
import os
import sys
import cv2
from controlnet_aux import OpenposeDetector
current_path = os.path.dirname(__file__)
sys.path.append(os.path.dirname(current_path))
sys.path.append(r'/home/mingjiahui/project/T2I-Adapter-XL')
from IPAdapter.util import load_model, set_parser


def main(args):
    # init
    image_dir = r'/home/mingjiahui/data/ipadapter/test_data/pose_lora/lora'
    save_dir = r'/home/mingjiahui/data/ipadapter/exp_pose/openpose'
    cond_img_dir = r'/home/mingjiahui/data/ipadapter/test_data/pose_lora/pose'
    os.makedirs(save_dir, exist_ok=True)

    # prepare
    # 1.image paths
    image_paths = [os.path.join(image_dir, name) for name in os.listdir(image_dir)][:1]
    # 2.scales
    scales = np.arange(0, 1.1, 0.1).tolist()
    # scales = [1]
    # 3.cond img
    cond_paths = [os.path.join(cond_img_dir, name) for name in os.listdir(cond_img_dir)][:1]

    # load detector
    # # 1.openpose
    class openpose_detector:
        def __init__(self, ):
            self.detector = OpenposeDetector.from_pretrained(
            '/mnt/nfs/file_server/public/mingjiahui/models/lllyasviel--ControlNet/annotator/ckpts'
        )

        def __call__(self, image_path, *args, **kwargs):
            img = Image.open(image_path)
            cond_img = self.detector(img, hand_and_face=True)

            cond_id = os.path.basename(cond_path).split('.')[0]
            cond_img.save(os.path.join(save_dir_, f'{cond_id}-canny.jpg'))
            return cond_img
    # # 2.canny
    class canny_detector:
        def __call__(self, image_path, *args, **kwargs):
            low_threshold = 200
            high_threshold = 300
            image = cv2.Canny(np.array(Image.open(image_path)), low_threshold, high_threshold)
            image = image[:, :, None]
            image = np.concatenate([image, image, image], axis=2)
            cond_img = Image.fromarray(image)

            cond_id = os.path.basename(cond_path).split('.')[0]
            cond_img.save(os.path.join(save_dir_, f'{cond_id}-canny.jpg'))
            return cond_img

    detector = openpose_detector()

    # load ip model
    print('test')
    print(r'loading model......')
    ip_model = load_model(
        base_model_path=args.base_model_path,
        image_encoder_path=args.image_encoder_path,
        ip_ckpt=args.ip_ckpt,
        vae_model_path=args.vae_model_path,
        unet_load=True, # load unetV1_1: encoder hidden states support input lists
        controlnet_model_path=args.controlnet_model_path,
    )

    # process
    for index, image_path in enumerate(image_paths):
        image_id = os.path.basename(image_path).split('.')[0]
        save_dir_ = os.path.join(save_dir, image_id)
        os.makedirs(save_dir_, exist_ok=True)
        image = Image.open(image_path).resize((512, 512))

        for cond_path in cond_paths:
            cond_img = detector(cond_path)        # canny_detector

            result = None
            for scale in scales:
                outputs = ip_model.generate(
                    pil_image=image,
                    image=cond_img,
                    num_samples=1,
                    num_inference_steps=20,
                    seed=42,
                    guidance_scale=7,
                    prompt='',
                    scale=scale,
                    cross_attention_kwargs={
                        'down_blocks': 'txt_img', 
                        'mid_block': 'txt_img', 
                        'up_blocks': 'txt_img',
                        },
                )

                out_put = np.array(outputs[0])
                result = cv2.hconcat([result, out_put]) if result is not None else out_put

            cond_id = os.path.basename(cond_path).split('.')[0]
            Image.fromarray(result).save(os.path.join(save_dir_, f'{cond_id}-result.jpg'))


if __name__ == '__main__':
    args = set_parser()

    main(args)
