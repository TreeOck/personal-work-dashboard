import * as THREE from "three";
import type { DeskModel } from "../data/model";
import type { materials } from "../scene/materials";
import { addCards, addStickies, addTray } from "./paperObjects";
import { addPenCup } from "./pens";
import { addBinders, addCalendar, addNotepad } from "./stationery";

export function buildObjects(scene: THREE.Scene, model: DeskModel, m: ReturnType<typeof materials>, matTop: number) {
  addCards(scene, model, m, matTop);
  addStickies(scene, model, m);
  addTray(scene, model, m, m.walnut);
  addPenCup(scene, model, m);
  addCalendar(scene, model, m);
  addNotepad(scene, model, m);
  addBinders(scene, m);
}
