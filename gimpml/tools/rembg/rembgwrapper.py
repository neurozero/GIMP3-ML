import os, sys
from PIL import Image

from rembg.bg import remove
from rembg.session_factory import new_session

# Import GIMP3-ML specific utilities
from gimpml.plugins.module_utils import *
from gimpml.plugins.rembg.constants import *


@handle_exceptions(PLUGIN_ID)
def main():
    weight_path = get_weight_path()
    data_output = get_model_config(PLUGIN_ID)
    force_cpu = data_output["force_cpu"]
    with Image.open(os.path.join(tmp_path, BASE_IMG)) as image:
        session = new_session(data_output["model_name"])
        output = remove(image, session=session,
            alpha_matting=data_output["alpha_matting"],
            alpha_matting_foreground_threshold=data_output["alpha_matting_foreground_threshold"],
            alpha_matting_background_threshold=data_output["alpha_matting_background_threshold"],
            alpha_matting_erode_size=data_output["alpha_matting_erode_size"],
            only_mask=data_output["only_mask"],
            post_process_mask=data_output["post_process_mask"]
        )
    output.save(os.path.join(tmp_path, RESULT_IMG), "PNG")
    set_model_config({
        "inference_status": "success",
        "force_cpu": force_cpu
    }, PLUGIN_ID)


if __name__ == "__main__":
    main()
