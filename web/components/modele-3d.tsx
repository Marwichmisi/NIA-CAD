"use client"

import { Suspense } from "react"
import { Canvas } from "@react-three/fiber"
import { OrbitControls, useGLTF } from "@react-three/drei"

function Scene({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  return <primitive object={scene} />
}

export function Modele3D({ url }: { url: string }) {
  return (
    <div
      data-testid="modele-3d"
      className="h-full min-h-64 w-full"
      role="img"
      aria-label="Modèle 3D de la carte"
    >
      <Canvas camera={{ position: [40, 40, 40], fov: 45 }}>
        <ambientLight intensity={0.9} />
        <directionalLight position={[50, 50, 50]} intensity={1.2} />
        <Suspense fallback={null}>
          <Scene url={url} />
        </Suspense>
        <OrbitControls enableDamping />
      </Canvas>
    </div>
  )
}
