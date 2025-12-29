import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
    startOnLoad: true,
    theme: 'dark',
    securityLevel: 'loose',
    fontFamily: 'Instrument Sans, sans-serif',
});

interface MermaidProps {
    chart: string;
}

const Mermaid: React.FC<MermaidProps> = ({ chart }) => {
    const ref = useRef<HTMLDivElement>(null);
    const [scale, setScale] = React.useState(1);
    const [panning, setPanning] = React.useState(false);
    const [position, setPosition] = React.useState({ x: 0, y: 0 });
    const lastFilter = useRef({ x: 0, y: 0 });

    useEffect(() => {
        if (ref.current && chart) {
            ref.current.removeAttribute('data-processed');
            // clear previous SVG
            ref.current.innerHTML = '';

            mermaid.contentLoaded();

            const renderChart = async () => {
                try {
                    const { svg } = await mermaid.render(`mermaid-${Math.random().toString(36).substr(2, 9)}`, chart);
                    if (ref.current) {
                        ref.current.innerHTML = svg;
                        // Force SVG to be fully visible regardless of container
                        const svgElement = ref.current.querySelector('svg');
                        if (svgElement) {
                            svgElement.style.width = '100%';
                            svgElement.style.height = 'auto';
                            svgElement.style.minWidth = '800px'; // Ensure it doesn't shrink too much
                        }
                    }
                } catch (e) {
                    console.error("Mermaid check failed:", e);
                    if (ref.current) {
                        ref.current.innerHTML = `<div class="text-red-400 text-xs p-4 border border-red-500/20 bg-red-500/10 rounded-lg">
                            <p class="font-bold mb-2">Visualization Warning</p>
                            <p>Could not render mind map structure. Attempting to show raw data:</p>
                            <pre class="mt-2 text-[10px] opacity-70 whitespace-pre-wrap">${chart.replace(/</g, '&lt;')}</pre>
                        </div>`;
                    }
                }
            };
            renderChart();
        }
    }, [chart]);

    const handleWheel = (e: React.WheelEvent) => {
        if (e.ctrlKey) {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            setScale(s => Math.min(Math.max(s * delta, 0.5), 5));
        }
    };

    return (
        <div className="relative w-full h-full overflow-hidden flex flex-col items-center justify-center bg-black/20 rounded-2xl border border-white/5">
            <div className="absolute top-4 right-4 z-10 flex gap-2 bg-black/50 p-1 rounded-lg backdrop-blur">
                <button onClick={() => setScale(s => Math.min(s + 0.25, 5))} className="p-2 hover:bg-white/10 rounded text-white font-bold text-xl leading-none">+</button>
                <button onClick={() => setScale(1)} className="p-2 hover:bg-white/10 rounded text-white text-xs px-3">Reset</button>
                <button onClick={() => setScale(s => Math.max(s - 0.25, 0.5))} className="p-2 hover:bg-white/10 rounded text-white font-bold text-xl leading-none">-</button>
            </div>

            <div
                className="w-full h-full overflow-auto p-8 cursor-move flex items-center justify-center"
                onWheel={handleWheel}
            // Simple drag scroll implementation could go here, but native scroll + zoom is often enough for v1
            >
                <div
                    ref={ref}
                    className="mermaid origin-center transition-transform duration-200 ease-out"
                    style={{ transform: `scale(${scale})` }}
                />
            </div>
        </div>
    );
};

export default Mermaid;
