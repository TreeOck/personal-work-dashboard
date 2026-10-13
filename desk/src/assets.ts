// Every asset the desk uses, inlined at build time as data URLs (?inline) or text (?raw).
// File names match desk/assets.lock.json.
import walnutMap from "../assets/textures/smoked_walnut_veneer_diffuse.jpg?inline";
import walnutNormal from "../assets/textures/smoked_walnut_veneer_nor_gl.jpg?inline";
import walnutRough from "../assets/textures/smoked_walnut_veneer_rough.jpg?inline";
import leatherMap from "../assets/textures/brown_leather_diffuse.jpg?inline";
import leatherNormal from "../assets/textures/brown_leather_nor_gl.jpg?inline";
import leatherRough from "../assets/textures/brown_leather_rough.jpg?inline";
import loftHall from "../assets/hdri/loft_hall.hdr?inline";
import cabin from "../assets/hdri/cabin.hdr?inline";
import lampGltf from "../assets/models/desk_lamp_arm_01/desk_lamp_arm_01.gltf?raw";
import lampBin from "../assets/models/desk_lamp_arm_01/desk_lamp_arm_01.bin?inline";
import lampDiff from "../assets/models/desk_lamp_arm_01/textures/desk_lamp_arm_01_diff_1k.jpg?inline";
import lampNor from "../assets/models/desk_lamp_arm_01/textures/desk_lamp_arm_01_nor_gl_1k.jpg?inline";
import lampArm from "../assets/models/desk_lamp_arm_01/textures/desk_lamp_arm_01_arm_1k.jpg?inline";
import plantGltf from "../assets/models/potted_plant_04/potted_plant_04.gltf?raw";
import plantBin from "../assets/models/potted_plant_04/potted_plant_04.bin?inline";
import plantDiff from "../assets/models/potted_plant_04/textures/potted_plant_04_diff_1k.jpg?inline";
import plantNor from "../assets/models/potted_plant_04/textures/potted_plant_04_nor_gl_1k.jpg?inline";
import plantArm from "../assets/models/potted_plant_04/textures/potted_plant_04_arm_1k.jpg?inline";
import caveat from "../assets/fonts/Caveat.ttf?inline";
import specialElite from "../assets/fonts/SpecialElite.ttf?inline";

export const ASSETS = {
  walnut: { map: walnutMap, normal: walnutNormal, rough: walnutRough },
  leather: { map: leatherMap, normal: leatherNormal, rough: leatherRough },
  hdri: { day: loftHall, evening: cabin },   // day: neutral loft-hall daylight (the old "blinds" room was 4x redder than blue)
  models: {
    lamp: { gltf: lampGltf, files: { "desk_lamp_arm_01.bin": lampBin, "textures/desk_lamp_arm_01_diff_1k.jpg": lampDiff,
      "textures/desk_lamp_arm_01_nor_gl_1k.jpg": lampNor, "textures/desk_lamp_arm_01_arm_1k.jpg": lampArm } },
    plant: { gltf: plantGltf, files: { "potted_plant_04.bin": plantBin, "textures/potted_plant_04_diff_1k.jpg": plantDiff,
      "textures/potted_plant_04_nor_gl_1k.jpg": plantNor, "textures/potted_plant_04_arm_1k.jpg": plantArm } },
  },
  fonts: { caveat, specialElite },
};
