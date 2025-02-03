#!/usr/bin/env python3
# coding: utf-8
"""
 .d8888b.  8888888 888b     d888 8888888b.       888b     d888 888
d88P  Y88b   888   8888b   d8888 888   Y88b      8888b   d8888 888
888    888   888   88888b.d88888 888    888      88888b.d88888 888
888          888   888Y88888P888 888   d88P      888Y88888P888 888
888  88888   888   888 Y888P 888 8888888P"       888 Y888P 888 888
888    888   888   888  Y8P  888 888             888  Y8P  888 888
Y88b  d88P   888   888   "   888 888             888   "   888 888
 "Y8888P88 8888888 888       888 888             888       888 88888888


Performs background removal on a given layer.
"""
import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, GimpUi, GObject, GLib, Gio, Gtk
import gettext, subprocess, os, sys, json
sys.path.extend([os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")])
from plugin_utils import *
from module_utils import *
from constants import *

_ = gettext.gettext

model_dict = {
    MODEL1: "u2net",
    MODEL2: "u2netp",
    MODEL3: "u2net_human_seg",
    MODEL4: "u2net_cloth_seg",
    MODEL5: "silueta", 
    MODEL6: "isnet_general_use",
    MODEL7: "isnet_anime",
    MODEL8: "sam",
    MODEL9: "birefnet_general",
    MODEL10: "birefnet_general_lite",
    MODEL11: "birefnet_portrait",
    MODEL12: "birefnet_dis",
    MODEL13: "birefnet_hrsod",
    MODEL14: "birefnet_cod",
    MODEL15: "birefnet_massive",
    }
model_name_enum = StringEnum(
    MODEL1,
    _(MODEL1),
    MODEL2,
    _(MODEL2),
    MODEL3,
    _(MODEL3),
    MODEL4,
    _(MODEL4),
    MODEL5,
    _(MODEL5),
    MODEL6,
    _(MODEL6),
    MODEL7,
    _(MODEL7),
    MODEL8,
    _(MODEL8),
    MODEL9,
    _(MODEL9),
    MODEL10,
    _(MODEL10),
    MODEL11,
    _(MODEL11),
    MODEL12,
    _(MODEL12),
    MODEL13,
    _(MODEL13),
    MODEL14,
    _(MODEL14),
    MODEL15,
    _(MODEL15),
)

def removebackground(
    procedure,
    image,
    n_drawables,
    layers,
    force_cpu,
    model_name,
    alpha_matting,
    alpha_matting_foreground_threshold,
    alpha_matting_background_threshold,
    alpha_matting_erode_size,
    only_mask,
    post_process_mask,
    progress_bar,
    config_path_output,
):
    # Save inference parameters and layers
    weight_path = config_path_output["weight_path"]
    python_path = config_path_output["python_path"]
    plugin_path = config_path_output["plugin_path"]

    undo_group_start(image)
    init_tmp()

    save_image(os.path.join(tmp_path, BASE_IMG), image, layers[0])
    set_model_config({
            "force_cpu": bool(force_cpu),
            "n_drawables": n_drawables,
            "model_name": model_dict[model_name],
            "alpha_matting":  bool(alpha_matting), # on | on/off
            "alpha_matting_foreground_threshold":  int(alpha_matting_foreground_threshold), # 240 | 0..255
            "alpha_matting_background_threshold":  int(alpha_matting_background_threshold), # 10 | 0..255
            "alpha_matting_erode_size":  int(alpha_matting_erode_size), # 10| 0..255
            "only_mask":  bool(only_mask), # off | on/off
            "post_process_mask": bool(post_process_mask), # off | on/off
            "inference_status": "started",
        }, PLUGIN_ID)

    # Run inference and load as layer
    subprocess.call([python_path, plugin_path])
    data_output = get_model_config(PLUGIN_ID)

    if data_output["inference_status"] == "success":
        load_single_result_and_insert(RESULT_IMG, image, "NoBackground")
        undo_group_end(image)
        cleanup_tmp() # Remove temporary images
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    else:
        undo_group_end(image)
        elog = "See GIMP console for error text"
        if "last_error" in data_output: elog = data_output["last_error"]
        show_dialog(
            "Background removal was not performed due to errors.\nError text:\n" + elog,
            "Error!", "error", image_paths
        )
        cleanup_tmp() # Remove temporary images
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def run(procedure, run_mode, image, n_drawables, layer, args, data):
    force_cpu = args.index(0)
    model_name = args.index(1)
    alpha_matting = args.index(2)
    alpha_matting_foreground_threshold = args.index(3)
    alpha_matting_background_threshold = args.index(4)
    alpha_matting_erode_size = args.index(5)
    only_mask = args.index(6)
    post_process_mask = args.index(7)

    if run_mode == Gimp.RunMode.INTERACTIVE:
        # Get all paths
        config_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "..", "..", "tools"
        )
        config_path_output = get_config()
        python_path = config_path_output["python_path"]
        config_path_output["plugin_path"] = os.path.join(config_path, PLUGIN_ID, "rembgwrapper.py")

        config = procedure.create_config()
        config.set_property("force_cpu", force_cpu)
        config.begin_run(image, run_mode, args)

        GimpUi.init("rembgwrapper.py")
        use_header_bar = Gtk.Settings.get_default().get_property(
            "gtk-dialogs-use-header"
        )

        if n_drawables != 1:
            show_dialog(
                "Please select a layer.", "Error !", "error", image_paths
            )
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

        n_drawables_text = _("Mask Selected |")

        # Create UI
        dialog = GimpUi.Dialog(use_header_bar=use_header_bar, title=_("Removing BG..."))
        dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("_Help"), Gtk.ResponseType.APPLY)
        dialog.add_button(_("_Remove"), Gtk.ResponseType.OK)

        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, homogeneous=False, spacing=10
        )
        dialog.get_content_area().add(vbox)
        vbox.show()

        # Create grid to set all the properties inside.
        grid = Gtk.Grid()
        grid.set_column_homogeneous(False)
        grid.set_border_width(10)
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        vbox.add(grid)
        grid.show()

        # Show Logo
        logo = Gtk.Image.new_from_file(image_paths["logo"])
        # grid.attach(logo, 0, 0, 1, 1)
        vbox.pack_start(logo, False, False, 1)
        logo.show()

        # Show License
        license_text = _(PLUGIN_LICENSE)
        label = Gtk.Label(label=license_text)
        # grid.attach(label, 1, 1, 1, 1)
        vbox.pack_start(label, False, False, 1)
        label.show()

        # Show n_drawables text
        label = Gtk.Label(label=n_drawables_text)
        grid.attach(label, 1, 0, 1, 1)
        label.show()

        # Show ideal image size text
        label = Gtk.Label(label="256 X 256 px")
        grid.attach(label, 2, 0, 1, 1)
        label.show()
            
        # Scale parameter
        # label = Gtk.Label.new_with_mnemonic(_("_AM:"))
        # grid.attach(label, 0, 1, 1, 1)
        # label.show()
        # spin = GimpUi.prop_spin_button_new(
        #     config, "alpha_matting", step_increment=1, page_increment=10, digits=3
        # )
        # grid.attach(spin, 1, 1, 1, 1)
        # spin.show()
        
        spin = GimpUi.prop_check_button_new(config, "alpha_matting", _("_Alpha Matting"))
        spin.set_tooltip_text(
            _(
                "If checked, Alpha Matting is turned on."
            )
        )
        grid.attach(spin, 1, 1, 1, 1)
        spin.show()
        
        # alpha_matting_foreground_threshold
        label = Gtk.Label.new_with_mnemonic(_("AM _FT:"))
        grid.attach(label, 2, 1, 1, 1)
        label.show()
        spin = GimpUi.prop_spin_button_new(
            config, "alpha_matting_foreground_threshold", step_increment=1, page_increment=10, digits=3
        )
        grid.attach(spin, 3, 1, 1, 1)
        spin.show()
        
        # alpha_matting_background_threshold
        label = Gtk.Label.new_with_mnemonic(_("AM _BT:"))
        grid.attach(label, 4, 1, 1, 1)
        label.show()
        spin = GimpUi.prop_spin_button_new(
            config, "alpha_matting_background_threshold", step_increment=1, page_increment=10, digits=3
        )
        grid.attach(spin, 5, 1, 1, 1)
        spin.show()
        
        # alpha_matting_erode_size
        label = Gtk.Label.new_with_mnemonic(_("AM _ES:"))
        grid.attach(label, 6, 1, 1, 1)
        label.show()
        spin = GimpUi.prop_spin_button_new(
            config, "alpha_matting_erode_size", step_increment=1, page_increment=10, digits=3
        )
        grid.attach(spin, 7, 1, 1, 1)
        spin.show()

        # only_mask
        spin = GimpUi.prop_check_button_new(config, "only_mask", _("Only _Mask"))
        spin.set_tooltip_text(
            _(
                "If checked, only mask will be used for inference."
            )
        )
        grid.attach(spin, 3, 0, 1, 1)
        spin.show()

        # post_process_mask
        spin = GimpUi.prop_check_button_new(config, "post_process_mask", _("_Postprocess Mask"))
        spin.set_tooltip_text(
            _(
                "If checked, the mask will be post-processed."
            )
        )
        grid.attach(spin, 1, 2, 1, 1)
        spin.show()
        
        # Force CPU parameter
        spin = GimpUi.prop_check_button_new(config, "force_cpu", _("Force _CPU"))
        spin.set_tooltip_text(
            _(
                "If checked, CPU is used for model inference."
                " Otherwise, GPU will be used if available."
            )
        )
        grid.attach(spin, 5, 0, 1, 1)
        spin.show()

        # Model Name parameter
        label = Gtk.Label.new_with_mnemonic(_("_Model Name:"))
        grid.attach(label, 6, 0, 1, 1)
        label.show()
        combo = GimpUi.prop_string_combo_box_new(
            config, "model_name", model_name_enum.get_tree_model(), 0, 1
        )
        grid.attach(combo, 7, 0, 1, 1)
        combo.show()

        progress_bar = Gtk.ProgressBar()
        vbox.add(progress_bar)
        progress_bar.show()

        # Wait for user to click
        dialog.show()
        while True:
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                force_cpu = config.get_property("force_cpu")
                model_name = config.get_property("model_name")
                alpha_matting = config.get_property("alpha_matting")
                alpha_matting_foreground_threshold = config.get_property("alpha_matting_foreground_threshold")
                alpha_matting_background_threshold = config.get_property("alpha_matting_background_threshold")
                alpha_matting_erode_size = config.get_property("alpha_matting_erode_size")
                only_mask = config.get_property("only_mask")
                post_process_mask = config.get_property("post_process_mask")
                print(f"Starting Remove: CPU={force_cpu}, Model={model_name}, Alpha Matting={alpha_matting}, FG={alpha_matting_foreground_threshold}, BG={alpha_matting_background_threshold}, Erode={alpha_matting_erode_size}, Only Mask={only_mask}, PP Mask={post_process_mask}")
                result = removebackground(
                    procedure,
                    image,
                    n_drawables,
                    layer,
                    force_cpu,
                    model_name,
                    alpha_matting,
                    alpha_matting_foreground_threshold,
                    alpha_matting_background_threshold,
                    alpha_matting_erode_size,
                    only_mask,
                    post_process_mask,
                    progress_bar,
                    config_path_output,
                )
                # If the execution was successful, save parameters so they will be restored next time we show dialog.
                if result.index(0) == Gimp.PDBStatusType.SUCCESS and config is not None:
                    config.end_run(Gimp.PDBStatusType.SUCCESS)
                return result
            elif response == Gtk.ResponseType.APPLY:
                url = HELP_URL + "item-7-1"
                Gio.app_info_launch_default_for_uri(url, None)
                continue
            else:
                dialog.destroy()
                return procedure.new_return_values(
                    Gimp.PDBStatusType.CANCEL, GLib.Error()
                )


class RemoveBG(Gimp.PlugIn):
    ## Parameters ##
    __gproperties__ = {
        "alpha_matting": (bool, _("_AM"), "Alpha matting; on/off (Default: on)", True, GObject.ParamFlags.READWRITE),
        "alpha_matting_foreground_threshold": (int, _("AM _FT"), "Alpha matting foreground threshold; 0..255 (Default: 240)", 0, 255, 240, GObject.ParamFlags.READWRITE),
        "alpha_matting_background_threshold": (int, _("AM _BT"), "Alpha matting background threshold; 0..255 (Default: 10)", 0, 255, 10, GObject.ParamFlags.READWRITE),
        "alpha_matting_erode_size": (int, _("AM _ES"), "Alpha matting erode size; 0..255 (Default: 10)", 0, 255, 10, GObject.ParamFlags.READWRITE),
        "only_mask": (bool, _("Only _Mask"), "Only mask; (Default: False)", False, GObject.ParamFlags.READWRITE),
        "post_process_mask": (bool, _("_Postprocess Mask"), "Postprocess mask; (Default: False)", False, GObject.ParamFlags.READWRITE),
        "force_cpu": (bool, _("Force _CPU"), "Force CPU; (Default: True)", True, GObject.ParamFlags.READWRITE),
        "model_name": (
            str,
            _("Model Name"),
            f"Model Name: '{MODEL1}', '{MODEL2}', '{MODEL3}', '{MODEL4}', '{MODEL5}', '{MODEL6}', '{MODEL7}', '{MODEL8}', '{MODEL9}', '{MODEL10}', '{MODEL11}', '{MODEL12}', '{MODEL13}', '{MODEL14}', '{MODEL15}'",
            MODEL1,
            GObject.ParamFlags.READWRITE
        ),
    }

    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return [PLUGIN_ID]

    def do_set_i18n(self, procname):
        return False, 'gimp30-python', None

    def do_create_procedure(self, name):
        procedure = None
        if name == PLUGIN_ID:
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, run, None
            )
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                N_("Performs background removal on a given image with GIMP mask layer."),
                globals()["__doc__"], 
                name,
            )
            procedure.set_menu_label(N_("_Remove BG..."))
            procedure.set_attribution(*ATTRIBUTION_INFO)
            procedure.add_menu_path(MENU_LOCATION)

            procedure.add_argument_from_property(self, "force_cpu")
            procedure.add_argument_from_property(self, "model_name")
            procedure.add_argument_from_property(self, "alpha_matting")
            procedure.add_argument_from_property(self, "alpha_matting_foreground_threshold")
            procedure.add_argument_from_property(self, "alpha_matting_background_threshold")
            procedure.add_argument_from_property(self, "alpha_matting_erode_size")
            procedure.add_argument_from_property(self, "only_mask")
            procedure.add_argument_from_property(self, "post_process_mask")
        return procedure


Gimp.main(RemoveBG.__gtype__, sys.argv)
