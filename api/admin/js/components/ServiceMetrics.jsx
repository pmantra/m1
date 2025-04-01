import React, { Component } from 'react';
import axios from 'axios';
import { uniqueId } from 'lodash';
import { LineChart } from 'react-chartkick';
import 'chart.js';

import '../bootstrap/css/bootstrap.scss';
import '../bootstrap/css/bootstrap-theme.scss';

class ServiceMetrics extends Component {
  constructor(props) {
    super(props);
    this.state = {
      charts: null,
      metrics: ['created_appointments', 'appointments_with_post_encounter_summary'],
      table: {},
    };
  }

  componentDidMount() {
    this.loadData();
  }

  loadData() {
    const { metrics } = this.state;

    if (metrics.length > 0) {
      axios.get(`/admin/service_metrics/metric?id=${metrics.join(',')}`).then((response) => {
        const charts = response.data;
        const table = {};
        charts.forEach(({ name, data }) => {
          Object.keys(data).forEach((date) => {
            if (!table[date]) {
              table[date] = {};
            }
            table[date][name] = data[date];
          });
        });
        this.setState({ charts, table });
      });
    } else {
      this.setState({ charts: null });
    }
  }

  toggleMetric(name) {
    const { metrics: currentMetrics } = this.state;
    let metrics = [...currentMetrics];

    if (metrics.includes(name)) {
      metrics = metrics.filter((metric) => metric !== name);
    } else {
      metrics.push(name);
    }

    this.setState({ metrics }, this.loadData);
  }

  render() {
    const { charts, metrics, table } = this.state;
    const {
      args: { allMetricNames },
    } = this.props;

    const columns = charts ? [...charts.map((chart) => chart.name)] : [];

    return (
      <div>
        {charts && (
          <div style={{ marginBottom: 10 }}>
            <LineChart data={charts} />
          </div>
        )}
        <div style={{ overflow: 'none', marginTop: 10 }}>
          <div style={{ width: '30%', float: 'left' }}>
            <b>Metrics</b>
            <div style={{ marginTop: 5 }}>
              {allMetricNames.map((name) => (
                <div key={name} style={{ marginBottom: 2 }}>
                  <label htmlFor="service-metrics-checkbox">
                    <input
                      id="service-metrics-checkbox"
                      type="checkbox"
                      style={{ marginRight: 5 }}
                      checked={metrics.includes(name)}
                      onChange={() => this.toggleMetric(name)}
                    />
                    <span>{name}</span>
                  </label>
                </div>
              ))}
            </div>
          </div>
          <div style={{ width: '70%', float: 'left' }}>
            <b>Results</b>
            <div style={{ marginTop: 5 }}>
              <table className="table">
                <thead>
                  <tr>
                    <td key={uniqueId()} />
                    {columns.map((metric) => (
                      <td key={uniqueId()} style={{ color: 'gray' }}>
                        {metric}
                      </td>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(table)
                    .sort()
                    .reverse()
                    .map((date) => (
                      <tr key={uniqueId()}>
                        <td key={uniqueId()}>{date}</td>
                        {columns.map((metric) => (
                          <td key={uniqueId()}>{table[date][metric] || 0}</td>
                        ))}
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  }
}

export default ServiceMetrics;
