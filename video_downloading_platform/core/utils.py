def transform_results(results):
    return [doc['_source'] for doc in results['hits']['hits']]


def transform_hl_results(results):
    ret = []
    for doc in results['hits']['hits']:
        d = {}
        for k, v in doc.items():
            if k.startswith('_'):
                k = k[1:]
            d[k] = v
        ret.append(d)
    return ret
