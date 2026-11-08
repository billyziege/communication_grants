/**
 * @generated SignedSource<<834863023560dde193b485ca90aa9d45>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* eslint-disable */

'use strict';

var node = (function(){
var v0 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "after"
},
v1 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "country"
},
v2 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "first"
},
v3 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "fundingMax"
},
v4 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "fundingMin"
},
v5 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "programmes"
},
v6 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "query"
},
v7 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "source"
},
v8 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "yearMax"
},
v9 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "yearMin"
},
v10 = {
  "kind": "Variable",
  "name": "query",
  "variableName": "query"
},
v11 = {
  "alias": null,
  "args": [
    (v10/*: any*/)
  ],
  "concreteType": "SearchFacets",
  "kind": "LinkedField",
  "name": "searchFacets",
  "plural": false,
  "selections": [
    {
      "alias": null,
      "args": null,
      "kind": "ScalarField",
      "name": "sources",
      "storageKey": null
    },
    {
      "alias": null,
      "args": null,
      "kind": "ScalarField",
      "name": "programmes",
      "storageKey": null
    },
    {
      "alias": null,
      "args": null,
      "kind": "ScalarField",
      "name": "countries",
      "storageKey": null
    }
  ],
  "storageKey": null
},
v12 = [
  {
    "kind": "Variable",
    "name": "after",
    "variableName": "after"
  },
  {
    "kind": "Variable",
    "name": "country",
    "variableName": "country"
  },
  {
    "kind": "Variable",
    "name": "first",
    "variableName": "first"
  },
  {
    "kind": "Variable",
    "name": "fundingMax",
    "variableName": "fundingMax"
  },
  {
    "kind": "Variable",
    "name": "fundingMin",
    "variableName": "fundingMin"
  },
  {
    "kind": "Variable",
    "name": "programmes",
    "variableName": "programmes"
  },
  (v10/*: any*/),
  {
    "kind": "Variable",
    "name": "source",
    "variableName": "source"
  },
  {
    "kind": "Variable",
    "name": "yearMax",
    "variableName": "yearMax"
  },
  {
    "kind": "Variable",
    "name": "yearMin",
    "variableName": "yearMin"
  }
];
return {
  "fragment": {
    "argumentDefinitions": [
      (v0/*: any*/),
      (v1/*: any*/),
      (v2/*: any*/),
      (v3/*: any*/),
      (v4/*: any*/),
      (v5/*: any*/),
      (v6/*: any*/),
      (v7/*: any*/),
      (v8/*: any*/),
      (v9/*: any*/)
    ],
    "kind": "Fragment",
    "metadata": null,
    "name": "GrantsPageSearchQuery",
    "selections": [
      (v11/*: any*/),
      {
        "args": (v12/*: any*/),
        "kind": "FragmentSpread",
        "name": "GrantList_query"
      }
    ],
    "type": "Query",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": [
      (v6/*: any*/),
      (v7/*: any*/),
      (v9/*: any*/),
      (v8/*: any*/),
      (v1/*: any*/),
      (v5/*: any*/),
      (v4/*: any*/),
      (v3/*: any*/),
      (v2/*: any*/),
      (v0/*: any*/)
    ],
    "kind": "Operation",
    "name": "GrantsPageSearchQuery",
    "selections": [
      (v11/*: any*/),
      {
        "alias": null,
        "args": (v12/*: any*/),
        "concreteType": "SearchGrantConnection",
        "kind": "LinkedField",
        "name": "search",
        "plural": false,
        "selections": [
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "totalCount",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "concreteType": "GrantNodeEdge",
            "kind": "LinkedField",
            "name": "edges",
            "plural": true,
            "selections": [
              {
                "alias": null,
                "args": null,
                "concreteType": "GrantNode",
                "kind": "LinkedField",
                "name": "node",
                "plural": false,
                "selections": [
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "id",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "title",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "organization",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "country",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "source",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "sourceId",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "sourceProgramme",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "sourceUrl",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "startDate",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "endDate",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "fundingAmount",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "fundingCurrency",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "__typename",
                    "storageKey": null
                  }
                ],
                "storageKey": null
              },
              {
                "alias": null,
                "args": null,
                "kind": "ScalarField",
                "name": "cursor",
                "storageKey": null
              }
            ],
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "concreteType": "PageInfo",
            "kind": "LinkedField",
            "name": "pageInfo",
            "plural": false,
            "selections": [
              {
                "alias": null,
                "args": null,
                "kind": "ScalarField",
                "name": "endCursor",
                "storageKey": null
              },
              {
                "alias": null,
                "args": null,
                "kind": "ScalarField",
                "name": "hasNextPage",
                "storageKey": null
              }
            ],
            "storageKey": null
          }
        ],
        "storageKey": null
      },
      {
        "alias": null,
        "args": (v12/*: any*/),
        "filters": [
          "query",
          "source",
          "yearMin",
          "yearMax",
          "country",
          "programmes",
          "fundingMin",
          "fundingMax"
        ],
        "handle": "connection",
        "key": "GrantList_search",
        "kind": "LinkedHandle",
        "name": "search"
      }
    ]
  },
  "params": {
    "cacheID": "14621bc2bbe02e8868fa061b5e6dbfa6",
    "id": null,
    "metadata": {},
    "name": "GrantsPageSearchQuery",
    "operationKind": "query",
    "text": "query GrantsPageSearchQuery(\n  $query: String!\n  $source: Source\n  $yearMin: Int\n  $yearMax: Int\n  $country: String\n  $programmes: [String!]\n  $fundingMin: Float\n  $fundingMax: Float\n  $first: Int\n  $after: String\n) {\n  searchFacets(query: $query) {\n    sources\n    programmes\n    countries\n  }\n  ...GrantList_query_VqWS4\n}\n\nfragment GrantCard_grant on GrantNode {\n  id\n  title\n  organization\n  country\n  source\n  sourceId\n  sourceProgramme\n  sourceUrl\n  startDate\n  endDate\n  fundingAmount\n  fundingCurrency\n}\n\nfragment GrantList_query_VqWS4 on Query {\n  search(query: $query, source: $source, yearMin: $yearMin, yearMax: $yearMax, country: $country, programmes: $programmes, fundingMin: $fundingMin, fundingMax: $fundingMax, first: $first, after: $after) {\n    totalCount\n    edges {\n      node {\n        id\n        ...GrantCard_grant\n        __typename\n      }\n      cursor\n    }\n    pageInfo {\n      endCursor\n      hasNextPage\n    }\n  }\n}\n"
  }
};
})();

node.hash = "a8684963e444c036daefc4459598e0d4";

export default node;
