import json
import requests
from PIL import Image
import time
import cv2
import argparse
from logger import logger
import os
import shutil
import numpy as np
import base64
import io

parser = argparse.ArgumentParser()
parser.add_argument("--target_h", type=int, default=768)
parser.add_argument("--target_w", type=int, default=768)
parser.add_argument("--output_path", help="output image path", required=True)
parser.add_argument("--params_path", type=str, help="params json", default="./temp.json")
parser.add_argument("--output_json", type=str, help="output status json", default="./status.json")
parser.add_argument("--port", type=str, help="port", default="7861")

# my add
parser.add_argument("--input_image", nargs='+', type=str)
parser.add_argument("--input_prompt", type=str)

args = parser.parse_args()


def pil_to_base64(pil_image):
    with io.BytesIO() as stream:
        pil_image.save(stream, "PNG", pnginfo=None)
        base64_str = str(base64.b64encode(stream.getvalue()), "utf-8")
        return "data:image/png;base64," + base64_str


def check_params(params_path, output_path, max_resolution=8000):
    code = 0
    error_str = ""

    output_dir = os.path.dirname(os.path.abspath(output_path))
    if not os.path.exists(output_dir):
        code = 4002
        error_str = "output dir %s is not exists" % output_dir
        return {'code': code, 'message': error_str}, None, None

    params = {}
    if params_path != "":
        params = json.load(open(args.params_path, "r"))

        if "steps" in params:
            try:
                steps = int(float(params['steps']))
            except Exception as e:
                error_str = "steps is not int"
                code = 4003
                return {'code': code, 'message': error_str}, None, None
        if "cfg_scale" in params:
            try:
                cfg_scale = float(params['cfg_scale'])
            except Exception as e:
                error_str = "cfg_scale is not float"
                code = 4004
                return {'code': code, 'message': error_str}, None, None
        if "height" in params:
            try:
                steps = int(float(params['height']))
            except Exception as e:
                error_str = "height is not int"
                code = 4006
                return {'code': code, 'message': error_str}, None, None
        if "width" in params:
            try:
                steps = int(float(params['width']))
            except Exception as e:
                error_str = "width is not int"
                code = 4007
                return {'code': code, 'message': error_str}, None, None
        if "seed" in params:
            if type(params['seed']) != int:
                error_str = "seed is not int"
                code = 4007
                return {'code': code, 'message': error_str}, None, None
        if "retry" in params:
            if type(params['retry']) != int:
                error_str = "retry is not int"
                code = 4007
                return {'code': code, 'message': error_str}, None, None
        if "prompt" in params:
            if type(params['prompt']) != str:
                error_str = "prompt is not string"
                code = 4008
                return {'code': code, 'message': error_str}, None, None
        if "negative_prompt" in params:
            if type(params['negative_prompt']) != str:
                error_str = "negative_prompt is not string"
                code = 4009
                return {'code': code, 'message': error_str}, None, None
        if "stages" in params:
            if len(params['stages']) > 0:
                denoising_strengths = params['stages']['denoising_strengths']
                step_ratios = params['stages']['step_ratios']
                if len(denoising_strengths) != len(step_ratios):
                    error_str = "the length of denoising_strengths is not equal to step_ratios"
                    code = 4010
                    return {'code': code, 'message': error_str}, None, None

    return {'code': code, 'message': error_str}, params


# @logger.catch(reraise=True)
def test_server(args, status_dict, params):
    if status_dict['code'] != 0:  # check 2, 7
        logger.error('Check params failed: code = {}'.format(status_dict['code']))
        try:
            shutil.copyfile(args.input_path, args.output_path)
        except Exception as e:
            status_dict['message'] += " and copy input to output fail"
            logger.error('Copy input to output failed!')
        with open(args.output_json, 'w') as f:
            json.dump(status_dict, f)
        return

    logger.info('Read port')
    url = "http://127.0.0.1:%s" % args.port
    # start_time = time.time()
    # print("start infer")
    # limit size to maxium resolution
    input_h = args.target_h
    input_w = args.target_w

    ratio = input_h / input_w
    if ratio > 1:
        input_h = 768
        input_w = int(768 / ratio)
    else:
        input_w = 768
        input_h = int(768 * ratio)

    # check if has control net
    if "alwayson_scripts" in params:
        for control in params["alwayson_scripts"]["controlnet"]["args"]:
            control["processor_res"] = min(input_h, input_w)

    stages = {}
    if "specifics" in params:
        specifics = params['specifics']
    if "stages" in params:
        stages = params['stages']

    params["output_path"] = args.output_path

    payload = {
        "seed": -1,
        "height": input_h,
        "width": input_w,
        "retry": 1,
        "stages": stages,
    }
    payload.update(params)

    if "prompt_distribution" in params:
        prompt_distribution = params["prompt_distribution"]
        prob = []
        attris = []
        for key in prompt_distribution:
            attris.append(key)
            prob.append(prompt_distribution[key])
        normal_prob = [p / sum(prob) for p in prob]
        value = np.random.choice(attris, p=normal_prob)
        payload["prompt"] += ", " + value

    if "negprompt_distribution" in params:
        negprompt_distribution = params["negprompt_distribution"]
        prob = []
        attris = []
        for key in negprompt_distribution:
            attris.append(key)
            prob.append(negprompt_distribution[key])
        normal_prob = [p / sum(prob) for p in prob]
        value = np.random.choice(attris, p=normal_prob)
        payload["negative_prompt"] += ", " + value

    payload['steps'] = int(float(payload['steps']))
    payload['cfg_scale'] = float(payload['cfg_scale'])
    payload['height'] = int(float(payload['height']))
    payload['width'] = int(float(payload['width']))
    payload_json = json.dumps(payload)
    try:
        logger.info('Request txt2img')
        response = requests.post(url=f'{url}/sdapi/v1/txt2img', data=payload_json).json()

        result = response['images'][0]
        image = Image.open(io.BytesIO(base64.b64decode(result.split(",", 1)[0])))
        if input_w <= args.target_w:
            image = image.resize((args.target_w, args.target_h), Image.BILINEAR)
        else:
            image = image.resize((args.target_w, args.target_h), Image.LANCZOS)
        image.save(args.output_path)
        return image

    except Exception as e:
        code = 5001
        logger.error(f'Cannot request to txt2img!')
        with open(args.output_json, 'w') as f:
            json.dump({'code': code, 'message': repr(e)}, f)
        return

        # logger.info(response)
    logger.info('Time elapsed: {}'.format(time.time() - start_time))

    with open(args.output_json, 'w') as f:
        json.dump({'code': 0, 'message': "SUCCESS"}, f)

    logger.info('======== End Server ========')
    return
#
#
# def merge():
#


if __name__ == "__main__":
    logger.info('======== Start Server ========')
    start_time = time.time()
    logger.info('Check params')
    status_dict, params = check_params(args.params_path, args.output_path)
    controlnet_params = params['alwayson_scripts']['controlnet']['args'][0]

    # get list(scale, prompt, image)
    scales = list(np.arange(0.1, 1, 0.1))
    print(scales)

    prompts = []
    with open(args.input_prompt, 'r')as file:
        lines = file.readlines()
        for line in lines:
            print(line.strip())
            prompts.append(line.strip())

    image_paths = []
    for txt_path in args.input_image:
        with open(txt_path, 'r')as file:
            lines = file.readlines()
        for line in lines:
            print(line.strip())
            image_paths.append(line.strip())

    save_dir=args.output_path
    os.makedirs(save_dir,exist_ok=True)
    print(f'save_dir:{save_dir}')

    for i_0, image_id in enumerate(image_paths):
        image_path = os.path.join(r'/mnt/nfs/file_server/public/', image_id)
        for i_1, prompt in enumerate(prompts):
            # outputs = []
            for scale in scales:
                controlnet_params['weight'] = scale
                controlnet_params['input_image'] = image_path
                params['prompt'] = prompt

                save_name = f"img_{i_0}-prompt_{i_1}-scale_{'{:.2f}'.format(scale)}.jpg"
                args.output_path = os.path.join(save_dir, save_name)
                test_server(args, status_dict, params)

            # merge_img()
