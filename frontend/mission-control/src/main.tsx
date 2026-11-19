import React from "react";
import {createRoot} from "react-dom/client";
import {Mission} from "./Mission";
import "./styles.css";
import "./mission.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><Mission/></React.StrictMode>);
