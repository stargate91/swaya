import PropTypes from 'prop-types';

const DashboardWidgetShell = ({ children, loading, size }) => {
  return (
    <div className={`dashboard-widget dashboard-widget--${size || 'md'}`}>
      {loading ? (
        <div className="dashboard-widget__loading">
          <div className="dashboard-spinner" />
        </div>
      ) : (
        <div className="dashboard-widget__content">{children}</div>
      )}
    </div>
  );
};

DashboardWidgetShell.propTypes = {
  children: PropTypes.node,
  loading: PropTypes.bool,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
};

export default DashboardWidgetShell;
