import { Link } from 'react-router-dom';
import { ErrorMessage, PageHeader } from '../../components/ui';
import { useAuth } from '../../auth/AuthContext';

export function AccessDenied() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader
        title="Acceso denegado"
        subtitle="No cuenta con los permisos necesarios para abrir esta sección"
      />
      <ErrorMessage message="Su perfil actual no tiene autorización para esta operación. Si considera que es un error, solicite al administrador la asignación del permiso correspondiente." />
      <section className="panel">
        <h2>Perfil actual</h2>
        <p>
          Usuario: <strong>{user?.username ?? '—'}</strong>
        </p>
        <p>
          Roles: {user?.roles.join(', ') || 'Sin roles asignados'}
        </p>
        <Link className="button button-primary" to="/">
          Volver al dashboard
        </Link>
      </section>
    </>
  );
}
