import Image from "next/image";

export function CustomIcon({ name }: { name: "plugin" | "skills" }) {
  return <Image alt="" aria-hidden="true" height={16} src={`/${name}.svg`} width={16} />;
}
