"use client";

import { Mesh, Program, Renderer, Triangle, Vec3 } from "ogl";
import { useEffect, useRef } from "react";
import styles from "./VoiceOrb.module.css";

export type VoiceOrbMode = "idle" | "listening" | "speaking";

const vertex = `
precision highp float;
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position, 0.0, 1.0); }
`;

const fragment = `
precision highp float;
uniform float iTime;
uniform vec3 iResolution;
uniform float hue;
uniform float hover;
uniform float rot;
uniform float hoverIntensity;
uniform float speechActivity;
uniform vec3 backgroundColor;
varying vec2 vUv;
vec3 rgb2yiq(vec3 color) { return vec3(dot(color,vec3(.299,.587,.114)),dot(color,vec3(.596,-.274,-.322)),dot(color,vec3(.211,-.523,.312))); }
vec3 yiq2rgb(vec3 color) { return vec3(color.x+.956*color.y+.621*color.z,color.x-.272*color.y-.647*color.z,color.x-1.106*color.y+1.703*color.z); }
vec3 adjustHue(vec3 color,float degrees) { float angle=degrees*3.14159265/180.;vec3 yiq=rgb2yiq(color);float cosine=cos(angle);float sine=sin(angle);yiq.yz=vec2(yiq.y*cosine-yiq.z*sine,yiq.y*sine+yiq.z*cosine);return yiq2rgb(yiq); }
vec3 hash33(vec3 point) { point=fract(point*vec3(.1031,.11369,.13787));point+=dot(point,point.yxz+19.19);return -1.+2.*fract(vec3(point.x+point.y,point.x+point.z,point.y+point.z)*point.zyx); }
float noise3(vec3 point) { const float k1=.333333333;const float k2=.166666667;vec3 cell=floor(point+(point.x+point.y+point.z)*k1);vec3 d0=point-(cell-(cell.x+cell.y+cell.z)*k2);vec3 edge=step(vec3(0.),d0-d0.yzx);vec3 i1=edge*(1.-edge.zxy);vec3 i2=1.-edge.zxy*(1.-edge);vec3 d1=d0-(i1-k2);vec3 d2=d0-(i2-k1);vec3 d3=d0-.5;vec4 falloff=max(.6-vec4(dot(d0,d0),dot(d1,d1),dot(d2,d2),dot(d3,d3)),0.);vec4 noise=falloff*falloff*falloff*falloff*vec4(dot(d0,hash33(cell)),dot(d1,hash33(cell+i1)),dot(d2,hash33(cell+i2)),dot(d3,hash33(cell+1.)));return dot(vec4(31.316),noise); }
vec4 extractAlpha(vec3 color) { float alpha=max(max(color.r,color.g),color.b);return vec4(color/(alpha+.00001),alpha); }
float lightLinear(float intensity,float attenuation,float distanceValue) { return intensity/(1.+distanceValue*attenuation); }
float lightQuadratic(float intensity,float attenuation,float distanceValue) { return intensity/(1.+distanceValue*distanceValue*attenuation); }
vec4 drawOrb(vec2 uv) { const float innerRadius=.6;const float noiseScale=.65;vec3 color1=adjustHue(vec3(.611765,.262745,.996078),hue);vec3 color2=adjustHue(vec3(.298039,.760784,.913725),hue);vec3 color3=adjustHue(vec3(.062745,.078431,.6),hue);float angle=atan(uv.y,uv.x);float lengthValue=length(uv);float inverseLength=lengthValue>0.?1./lengthValue:0.;float backgroundLuminance=dot(backgroundColor,vec3(.299,.587,.114));float n0=noise3(vec3(uv*noiseScale,iTime*.5))*.5+.5;float radius=mix(mix(innerRadius,1.,.4),mix(innerRadius,1.,.6),n0);float edgeDistance=distance(uv,(radius*inverseLength)*uv);float rim=lightLinear(1.,10.,edgeDistance);rim*=smoothstep(radius*1.05,radius,lengthValue);float innerFade=smoothstep(radius*.8,radius*.95,lengthValue);rim*=mix(innerFade,1.,backgroundLuminance*.7);float colorBlend=cos(angle+iTime*2.)*.5+.5;float lightAngle=iTime*-1.;vec2 lightPosition=vec2(cos(lightAngle),sin(lightAngle))*radius;float lightDistance=distance(uv,lightPosition);float movingLight=lightQuadratic(1.5,5.,lightDistance);movingLight*=lightLinear(1.,50.,edgeDistance);float outerMask=smoothstep(1.,mix(innerRadius,1.,n0*.5),lengthValue);float innerMask=smoothstep(innerRadius,mix(innerRadius,1.,.5),lengthValue);vec3 colorBase=mix(color1,color2,colorBlend);float fadeAmount=mix(1.,.1,backgroundLuminance);vec3 darkColor=mix(color3,colorBase,rim);darkColor=(darkColor+movingLight)*outerMask*innerMask;darkColor=clamp(darkColor,0.,1.);vec3 lightColor=(colorBase+movingLight)*mix(1.,outerMask*innerMask,fadeAmount);lightColor=mix(backgroundColor,lightColor,rim);lightColor=clamp(lightColor,0.,1.);vec3 finalColor=mix(darkColor,lightColor,backgroundLuminance);return extractAlpha(finalColor); }
void main() { vec2 center=iResolution.xy*.5;float size=min(iResolution.x,iResolution.y);vec2 uv=(vUv*iResolution.xy-center)/size*2.;float sine=sin(rot);float cosine=cos(rot);uv=vec2(cosine*uv.x-sine*uv.y,sine*uv.x+cosine*uv.y);float distortion=hover+speechActivity;uv.x+=distortion*hoverIntensity*.1*sin(uv.y*10.+iTime);uv.y+=distortion*hoverIntensity*.1*sin(uv.x*10.+iTime);vec4 color=drawOrb(uv);gl_FragColor=vec4(color.rgb*color.a,color.a); }
`;

export function VoiceOrb({ audioLevel, hue, mode }: { audioLevel: number; hue: number; mode: VoiceOrbMode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const modeRef = useRef(mode);
  const levelRef = useRef(audioLevel);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { levelRef.current = audioLevel; }, [audioLevel]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const renderer = new Renderer({ alpha: true, premultipliedAlpha: false });
    const gl = renderer.gl;
    const program = new Program(gl, { vertex, fragment, transparent: true, uniforms: { iTime: { value: 0 }, iResolution: { value: new Vec3() }, hue: { value: hue }, hover: { value: 0 }, rot: { value: 0 }, hoverIntensity: { value: 2 }, speechActivity: { value: 0 }, backgroundColor: { value: new Vec3(0, 0, 0) } } });
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });
    container.appendChild(gl.canvas);
    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio, 2);
      renderer.setSize(container.clientWidth * ratio, container.clientHeight * ratio);
      gl.canvas.style.width = `${container.clientWidth}px`;
      gl.canvas.style.height = `${container.clientHeight}px`;
      program.uniforms.iResolution.value.set(gl.canvas.width, gl.canvas.height, gl.canvas.width / gl.canvas.height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    let hover = 0;
    const move = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      hover = Math.hypot(event.clientX - rect.left - rect.width / 2, event.clientY - rect.top - rect.height / 2) < Math.min(rect.width, rect.height) * .4 ? 1 : 0;
    };
    const leave = () => { hover = 0; };
    container.addEventListener("mousemove", move);
    container.addEventListener("mouseleave", leave);
    let frame = 0;
    let previous = 0;
    let elapsed = 0;
    let rotation = 0;
    let speech = 0;
    const render = (time: number) => {
      const delta = Math.min((time - previous) * .001, .1);
      previous = time;
      const level = Math.min(Math.max(levelRef.current, 0), 1);
      speech += ((modeRef.current === "speaking" ? .16 + level * .34 : 0) - speech) * .12;
      elapsed += delta * (modeRef.current === "speaking" ? 1.2 + level : modeRef.current === "listening" ? .62 : .34);
      program.uniforms.iTime.value = elapsed;
      program.uniforms.hover.value += (hover - program.uniforms.hover.value) * .1;
      program.uniforms.speechActivity.value = speech;
      rotation += delta * (hover > .5 ? .3 : modeRef.current === "speaking" ? level * .16 : 0);
      program.uniforms.rot.value = rotation;
      renderer.render({ scene: mesh });
      frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); container.removeEventListener("mousemove", move); container.removeEventListener("mouseleave", leave); gl.canvas.remove(); gl.getExtension("WEBGL_lose_context")?.loseContext(); };
  }, [hue]);
  return <div className={styles.orb} data-mode={mode} ref={containerRef} />;
}
