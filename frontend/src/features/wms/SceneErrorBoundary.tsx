import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Icon } from '../../components/Icon';

interface Props {
  children: ReactNode;
  onFallback: () => void;
}

interface State {
  failed: boolean;
}

/** Aísla fallos de WebGL/Three.js para que la vista 2D siga disponible. */
export class SceneErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('La escena 3D no pudo renderizarse.', error.message, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <div className="webgl-fallback" role="alert">
          <Icon name="alert" size={20} />
          <h3>La vista 3D no pudo iniciarse</h3>
          <p>Se conserva la vista 2D con las mismas ubicaciones y existencias del WMS.</p>
          <button type="button" className="button button-primary" onClick={this.props.onFallback}>
            Volver a la vista 2D
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
