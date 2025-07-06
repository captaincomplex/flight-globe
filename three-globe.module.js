import * as THREE from 'https://unpkg.com/three@0.150.0/build/three.module.js';

export default function ThreeGlobe() {
  const globeObj = new THREE.Object3D();
  globeObj.globeImageUrl = () => globeObj;
  globeObj.arcsData = () => globeObj;
  globeObj.arcColor = () => globeObj;
  globeObj.arcDashLength = () => globeObj;
  globeObj.arcDashGap = () => globeObj;
  globeObj.arcDashInitialGap = () => globeObj;
  globeObj.arcDashAnimateTime = () => globeObj;
  globeObj.arcAltitudeAutoScale = () => globeObj;
  return globeObj;
}
