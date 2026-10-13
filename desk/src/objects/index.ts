import * as THREE from "three";
import type { DeskModel } from "../data/model";
import { Registry } from "../scene/focusables";
import type { materials } from "../scene/materials";
import { addCards, addStickies, addTray } from "./paperObjects";
import { addPenCup } from "./pens";
import { addBinders, addCalendar, addNotepad } from "./stationery";

export function buildObjects(scene: THREE.Scene, model: DeskModel, m: ReturnType<typeof materials>, matTop: number): Registry {
  const reg = new Registry();
  addCards(scene, model, m, matTop, reg);
  addStickies(scene, model, m, reg);
  addTray(scene, model, m, m.walnut);
  addPenCup(scene, model, m);
  addCalendar(scene, model, m, reg);
  addNotepad(scene, model, m, reg);
  addBinders(scene, m);
  return reg;
}
