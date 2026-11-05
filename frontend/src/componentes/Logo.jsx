import llama from "../assets/llama.png";
import palabra from "../assets/bruto-blanco.png";

// La llama y la palabra BRUTO, como arriba de las pantallas de la maqueta
export default function Logo({ chico = false }) {
  return (
    <div className="flex items-center gap-2">
      <img src={llama} alt="" className={chico ? "w-5" : "w-6"} />
      <img src={palabra} alt="BRUTO" className={chico ? "w-14" : "w-[68px]"} />
    </div>
  );
}
